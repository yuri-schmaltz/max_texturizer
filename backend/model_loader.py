import os
import logging
import importlib
import threading
from contextlib import nullcontext
from unittest.mock import patch
try:
    import torch
except ImportError:
    torch = None

logger = logging.getLogger("max-texturizer-backend")

class ModelLoader:
    def __init__(self):
        self.paint_pipeline = None
        self.device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
        self.is_mock = True
        self.load_error = None
        self._paint_lock = threading.Lock()

    def load_models(self, force_mock=False, require_real=False):
        """
        Attempts to load the Hunyuan3D-Paint model.
        Falls back to mock mode if CUDA is unavailable, weights are missing, or force_mock is True.
        """
        self.paint_pipeline = None
        self.is_mock = True
        self.load_error = None
        if force_mock:
            logger.info("Mock Mode forced via configuration. Running in Mock Mode.")
            self.is_mock = True
            return

        if torch is None or not torch.cuda.is_available():
            self._load_failed("PyTorch com CUDA indisponível. Execute ./run_backend.sh --real.", require_real)
            return

        try:
            logger.info("Attempting to import hy3dgen and load Hunyuan3D-Paint...")
            # Import hy3dgen dynamically to prevent import errors if packages aren't fully compiled
            from hy3dgen.texgen import Hunyuan3DPaintPipeline
            
            # Load the paint pipeline
            # Typically looks for tencent/Hunyuan3D-2.1 or tencent/Hunyuan3D-2 on HuggingFace
            model_id = os.getenv("HUNYUAN3D_MODEL_ID", "tencent/Hunyuan3D-2")
            logger.info(f"Loading pipeline weights from: {model_id}")
            # This wrapper places its internal models on CUDA itself; it has no .to().
            pipeline = Hunyuan3DPaintPipeline.from_pretrained(model_id)
            if os.getenv("HUNYUAN3D_CPU_OFFLOAD", "true").lower() == "true":
                pipeline.enable_model_cpu_offload()
            self.paint_pipeline = pipeline
            self.is_mock = False
            logger.info("Hunyuan3D-Paint model loaded successfully!")
        except Exception as e:
            self._load_failed(f"Falha ao carregar Hunyuan3D-Paint: {e}. Execute ./run_backend.sh --real para instalar/verificar hy3dgen e suas extensões.", require_real)

    def _load_failed(self, message, require_real):
        self.paint_pipeline = None
        self.is_mock = True
        self.load_error = message
        if require_real:
            raise RuntimeError(message)
        logger.warning("%s Usando modo Mock.", message)

    def paint_mesh(self, mesh, image, **kwargs):
        """
        Textures an input trimesh using the loaded Hunyuan3D-Paint model.
        """
        if self.is_mock or self.paint_pipeline is None:
            raise RuntimeError("Hunyuan3D-Paint model is not loaded. Current state is Mock Mode.")
        
        # The pipeline accepts a trimesh.Trimesh object and a PIL Image
        # Returns a textured trimesh object
        logger.info("Running texture generation on the input mesh...")
        with self._paint_lock:
            preserve_uv = kwargs.get('preserve_uv', False)
            if preserve_uv:
                from texture_utils import validate_preserved_uv
                validate_preserved_uv(mesh)
            resolution = kwargs.get('resolution')
            if resolution is not None:
                self.paint_pipeline.config.texture_size = resolution
                self.paint_pipeline.render.set_default_texture_resolution(resolution)
            # The upstream wrapper always unwraps with xatlas. Skip only that step
            # for validated UVs, under the same lock protecting its shared renderer.
            module = importlib.import_module(type(self.paint_pipeline).__module__)
            uv_context = patch.object(module, 'mesh_uv_wrap', lambda value: value) if preserve_uv else nullcontext()
            with uv_context:
                return self.paint_pipeline(mesh, image=image)

# Global model loader instance
model_loader = ModelLoader()
