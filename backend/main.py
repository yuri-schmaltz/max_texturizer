import os
import io
import zipfile
import logging
import uuid
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
from llm_orchestrator import llm_orchestrator

app = FastAPI(
    title="Max Texturizer API",
    description="Backend for automatic texturing of 3D meshes using Hunyuan3D-Paint",
    version="1.1.0"
)

class OrchestrateRequest(BaseModel):
    prompt: str
    slots: List[str]
    model_url: Optional[str] = "http://localhost:11434"
    model_name: Optional[str] = "llama3"

# Initialize models on startup
@app.on_event("startup")
def startup_event():
    # By default, we attempt to load real models unless forced or no GPU
    force_mock = os.getenv("FORCE_MOCK", "false").lower() == "true"
    model_loader.load_models(force_mock=force_mock)

@app.get("/health")
def health_check():
    """
    Returns server status, whether running in Mock Mode, and target device.
    """
    return {
        "status": "running",
        "is_mock": model_loader.is_mock,
        "device": model_loader.device,
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
def generate_ref_image(
    prompt: str = Query(..., description="Prompt to generate image from"),
    force_mock: bool = Query(False, description="Force generator to output mock image")
):
    """
    Generates a reference image from a text prompt.
    If in mock mode or forced, generates a beautiful gradient image using PIL with text.
    """
    logger.info(f"Generating reference image for prompt: '{prompt}'")
    
    # Check if we should generate a mock reference image
    if model_loader.is_mock or force_mock:
        # Generate a beautiful gradient image as a mock preview
        res = 512
        img = Image.new("RGB", (res, res), (30, 30, 40))
        draw = ImageDraw.Draw(img)
        
        # Draw abstract background gradient based on prompt hash to make it dynamic
        hue = hash(prompt) % 360
        # Simple color generation in RGB from hue
        import colorsys
        c1 = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(hue / 360.0, 0.6, 0.4))
        c2 = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(((hue + 180) % 360) / 360.0, 0.6, 0.2))
        
        for y in range(res):
            blend = y / res
            r = int(c1[0] * (1 - blend) + c2[0] * blend)
            g = int(c1[1] * (1 - blend) + c2[1] * blend)
            b = int(c1[2] * (1 - blend) + c2[2] * blend)
            draw.line([(0, y), (res, y)], fill=(r, g, b))
            
        # Draw some circles/shapes
        draw.ellipse([res//4, res//4, 3*res//4, 3*res//4], outline=(255, 255, 255, 100), width=3)
        
        # Write prompt on the image
        draw.text((20, res - 50), f"PROMPT: {prompt[:40]}...", fill=(255, 255, 255))
        draw.text((20, 20), "MOCK GENERATION PREVIEW", fill=(255, 255, 200))
        
        # Save to buffer
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    
    else:
        # If in real mode, we could trigger a local lightweight Text-to-Image pipeline
        # or use a free public API endpoint (HuggingFace Inference API etc.)
        # For maximum robustness in this local server setup, we fall back to the generator
        # if the real HuggingFace API calls fail or offline.
        try:
            import requests
            # Using a free public stable diffusion API (e.g., Pollinations AI or standard SD)
            # This is extremely fast, lightweight and works perfectly for reference image previews!
            logger.info("Fetching image from public Stable Diffusion API...")
            sanitized_prompt = requests.utils.quote(prompt)
            api_url = f"https://image.pollinations.ai/p/{sanitized_prompt}?width=512&height=512&seed=42&nologo=true"
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                return Response(content=response.content, media_type="image/jpeg")
        except Exception as e:
            logger.warning(f"Failed to fetch from public Text-to-Image API: {e}. Falling back to local gradient generator.")
            
        # Fallback to local procedural gradient if offline
        return generate_ref_image(prompt, force_mock=True)

@app.post("/texture")
async def texture_mesh(
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    resolution: int = Form(1024),
    steps: int = Form(20),
    guidance_scale: float = Form(7.5),
    negative_prompt: Optional[str] = Form(""),
    force_mock: bool = Form(False)
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
        # Determine if we run in mock mode
        use_mock = model_loader.is_mock or force_mock
        
        # 1. Obtain reference image (either generated from prompt or using prompt to generate mock texture)
        ref_image = None
        if prompt and not use_mock:
            # Let's fetch the reference image using our own helper
            try:
                import requests
                logger.info(f"Generating reference image via API for prompt: '{prompt}'")
                sanitized_prompt = requests.utils.quote(prompt)
                api_url = f"https://image.pollinations.ai/p/{sanitized_prompt}?width=512&height=512&seed=42&nologo=true"
                response = requests.get(api_url, timeout=15)
                if response.status_code == 200:
                    ref_image = Image.open(io.BytesIO(response.content)).convert("RGB")
            except Exception as e:
                logger.warning(f"Could not generate reference image for AI painter: {e}. Proceeding without image cond.")
        
        # 2. Texturing stage
        if use_mock:
            logger.info("Processing using Mock Generator...")
            mesh_out, albedo, roughness, normal = apply_mock_texture_to_mesh(
                input_mesh_path, prompt, ref_image=ref_image, resolution=resolution
            )
        else:
            logger.info("Processing using Hunyuan3D-Paint...")
            # Load mesh in trimesh
            import trimesh
            mesh_in = trimesh.load(input_mesh_path, force='mesh')
            
            # If we don't have a reference image, generate one or raise error
            if ref_image is None:
                raise HTTPException(status_code=400, detail="A text prompt is required to generate reference image for the texturing pipeline.")
            
            # Call Hunyuan3D-Paint
            # We pass steps, guidance scale etc as kwargs
            mesh_out = model_loader.paint_mesh(
                mesh_in, ref_image, 
                steps=steps, 
                guidance_scale=guidance_scale,
                negative_prompt=negative_prompt
            )
            
            # Extract maps from materials if returned, or we generate default maps for output bundle
            # Since Hunyuan3D-Paint maps the textures onto the mesh directly, we can export the GLB.
            # We can also extract the texture image to return in the ZIP.
            albedo = None
            if hasattr(mesh_out.visual, 'material') and mesh_out.visual.material is not None:
                material = mesh_out.visual.material
                if hasattr(material, 'image') and material.image is not None:
                    albedo = material.image
                    
            if albedo is None:
                # Fallback to simple image extraction if simple color/texture
                albedo = Image.new("RGB", (resolution, resolution), (180, 180, 180))
            
            # Create default roughness and normals since Hunyuan3D v2.0/v2.1 paint pipeline
            # primarily outputs Albedo. PBR maps are often generated procedurally or via additional outputs.
            _, roughness, normal = generate_procedural_textures(prompt, ref_image, resolution)

        # 3. Export the textured mesh to GLB
        output_glb_bytes = mesh_out.export(file_type="glb")
        
        # 4. Pack everything into a ZIP archive
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zip_file:
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
    uvicorn.run("main:app", host=host, port=port, reload=True)
