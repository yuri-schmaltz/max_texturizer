import os
import io
import zipfile
import logging
import uuid
import json
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("max-texturizer-backend")

# Import our custom modules
from model_loader import model_loader
from mock_generator import apply_mock_texture_to_mesh, generate_procedural_textures
from reference_images import reference_image, pattern_kind
from texture_utils import apply_pattern, extract_albedo, neutral_maps
from llm_orchestrator import llm_orchestrator

@asynccontextmanager
async def lifespan(app):
    force_mock = os.getenv("FORCE_MOCK", "false").lower() == "true"
    require_real = os.getenv("REQUIRE_REAL", "false").lower() == "true"
    model_loader.load_models(force_mock=force_mock, require_real=require_real)
    yield


app = FastAPI(
    title="Max Texturizer API",
    description="Backend for automatic texturing of 3D meshes using Hunyuan3D-Paint",
    version="1.4.0",
    lifespan=lifespan,
)

class OrchestrateRequest(BaseModel):
    prompt: str
    slots: List[str]
    model_url: Optional[str] = "http://localhost:11434"
    model_name: Optional[str] = "llama3"

@app.get("/health")
def health_check():
    """
    Returns server status, whether running in Mock Mode, and target device.
    """
    return {
        "status": "running",
        "is_mock": model_loader.is_mock,
        "device": model_loader.device,
        "load_error": model_loader.load_error,
        "texture_api_version": 2,
        "mode": "Mock Mode (Procedural)" if model_loader.is_mock else "AI Model Mode (Hunyuan3D-Paint)"
    }

@app.post("/orchestrate")
def orchestrate_materials(req: OrchestrateRequest):
    """
    Orchestrates texture parameters for a list of Blender material slots using a local LLM.
    """
    try:
        result = llm_orchestrator.orchestrate(
            prompt=req.prompt,
            slots=req.slots,
            model_url=req.model_url,
            model_name=req.model_name
        )
        return result
    except Exception as e:
        logger.error(f"Orchestration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate-ref-image")
def generate_ref_image(prompt: str = Query(...), force_mock: bool = Query(False),
                       method: str = Query("AUTO"), resolution: int = Query(1024, ge=128, le=4096)):
    try:
        if force_mock:
            image, _, _ = generate_procedural_textures(prompt, resolution=resolution)
            source = "mock"
        else:
            image, source = reference_image(prompt, resolution, method)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png", headers={"X-Reference-Source": source})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Falha ao gerar imagem de referência. Selecione uma imagem local ou tente novamente. " + str(error)) from error

@app.post("/texture")
async def texture_mesh(
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    resolution: int = Form(1024, ge=128, le=4096),
    steps: int = Form(20),
    guidance_scale: float = Form(7.5),
    negative_prompt: Optional[str] = Form(""),
    force_mock: bool = Form(False),
    method: str = Form("AUTO"),
    preserve_uv: bool = Form(False),
    reference: Optional[UploadFile] = File(None),
    reference_source: str = Form("uploaded"),
):
    """
    Textures an uploaded 3D mesh (OBJ or GLB) based on prompt or uploaded reference image.
    Returns a ZIP containing the textured mesh (mesh.glb), albedo, roughness, and normal maps.
    """
    logger.info(f"Received texturing request. Mesh filename: {file.filename}, Resolution: {resolution}")
    
    # Save input mesh to a temporary file
    temp_dir = "/tmp/max-texturizer"
    os.makedirs(temp_dir, exist_ok=True)
    temp_id = str(uuid.uuid4())
    
    # Detect extension
    ext = ".glb"
    if file.filename.lower().endswith(".obj"):
        ext = ".obj"
        
    input_mesh_path = os.path.join(temp_dir, f"input_{temp_id}{ext}")
    
    with open(input_mesh_path, "wb") as buffer:
        buffer.write(await file.read())
        
    try:
        if method not in {"AUTO", "AI", "PATTERN"}:
            raise HTTPException(status_code=422, detail="Método de geração inválido.")
        direct_pattern = method == "PATTERN" or (method == "AUTO" and pattern_kind(prompt or "")
                           and (reference is None or reference_source == "local-pattern"))
        use_mock = force_mock
        if model_loader.is_mock and not force_mock and not direct_pattern:
            raise HTTPException(status_code=503, detail="O modelo de IA não está carregado. Use padrões locais, inicie o modo real ou ative Mock explicitamente para testes.")
        ref_image = None
        source = None
        if reference is not None:
            try:
                ref_image = Image.open(io.BytesIO(await reference.read())).convert("RGB")
                source = "uploaded"
            except Exception as error:
                raise HTTPException(status_code=422, detail="Imagem de referência inválida.") from error
        if use_mock:
            mesh_out, albedo, roughness, normal = apply_mock_texture_to_mesh(
                input_mesh_path, prompt, ref_image=ref_image, resolution=resolution)
            engine = "mock"
        else:
            import trimesh
            mesh_in = trimesh.load(input_mesh_path, force='mesh', process=False)
            if ref_image is None:
                if not prompt or not prompt.strip():
                    raise HTTPException(status_code=422, detail="Informe um prompt ou selecione uma imagem de referência.")
                try:
                    ref_image, source = reference_image(prompt, resolution, "PATTERN" if direct_pattern else "AI")
                except ValueError as error:
                    raise HTTPException(status_code=422, detail=str(error)) from error
                except Exception as error:
                    raise HTTPException(status_code=502, detail="O serviço de referência falhou. Selecione uma imagem local; nenhuma textura foi gerada. " + str(error)) from error
            if direct_pattern:
                albedo = ref_image.resize((resolution, resolution), Image.Resampling.LANCZOS)
                mesh_out = apply_pattern(mesh_in, albedo, preserve_uv)
                engine = "local-pattern"
            else:
                mesh_out = model_loader.paint_mesh(mesh_in, ref_image, resolution=resolution, preserve_uv=preserve_uv)
                albedo = extract_albedo(mesh_out)
                engine = "hunyuan3d"
            # Paint v2.0 supplies albedo only; don't invent bumps or checkerboard PBR details.
            roughness, normal = neutral_maps(albedo.width)
        metadata = {"engine": engine, "reference_source": source, "preserve_uv": preserve_uv,
                    "resolution": list(albedo.size), "auxiliary_maps": "neutral" if not use_mock else "mock"}
        logger.info("Texturing result: %s", metadata)

        # 3. Export the textured mesh to GLB
        output_glb_bytes = mesh_out.export(file_type="glb")
        
        # 4. Pack everything into a ZIP archive
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("generation.json", json.dumps(metadata))
            # Add textured mesh
            zip_file.writestr("mesh.glb", output_glb_bytes)
            
            # Add separate textures for option B (Material Application)
            albedo_buf = io.BytesIO()
            albedo.save(albedo_buf, format="PNG")
            zip_file.writestr("albedo.png", albedo_buf.getvalue())
            
            roughness_buf = io.BytesIO()
            roughness.save(roughness_buf, format="PNG")
            zip_file.writestr("roughness.png", roughness_buf.getvalue())
            
            normal_buf = io.BytesIO()
            normal.save(normal_buf, format="PNG")
            zip_file.writestr("normal.png", normal_buf.getvalue())

        zip_buf.seek(0)
        logger.info("Successfully packaged zip archive for client!")
        
        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=textured_{temp_id}.zip"}
        )

    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as e:
        logger.error(f"Error occurred during texturing process: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Texturing failed: {str(e)}")
        
    finally:
        # Cleanup input temp file
        if os.path.exists(input_mesh_path):
            os.remove(input_mesh_path)

if __name__ == "__main__":
    import uvicorn
    # Read host/port from environment
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8009))
    uvicorn.run("main:app", host=host, port=port, reload=os.getenv("RELOAD", "false").lower() == "true")
