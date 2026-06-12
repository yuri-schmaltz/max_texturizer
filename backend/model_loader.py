import os
import logging
import torch

logger = logging.getLogger("max-texturizer-backend")

class ModelLoader:
    def __init__(self):
        self.paint_pipeline = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.is_mock = True

    def load_models(self, force_mock=False):
        """
        Attempts to load the Hunyuan3D-Paint model.
        Falls back to mock mode if CUDA is unavailable, weights are missing, or force_mock is True.
        """
        if force_mock:
            logger.info("Mock Mode forced via configuration. Running in Mock Mode.")
            self.is_mock = True
            return

        if not torch.cuda.is_available():
            logger.warning("CUDA is not available on this machine. Falling back to Mock Mode.")
            self.is_mock = True
            return

        try:
            logger.info("Attempting to import hy3dgen and load Hunyuan3D-Paint...")
            # Import hy3dgen dynamically to prevent import errors if packages aren't fully compiled
            from hy3dgen.texgen import Hunyuan3DPaintPipeline
            
            # Load the paint pipeline
            # Typically looks for tencent/Hunyuan3D-2.1 or tencent/Hunyuan3D-2 on HuggingFace
            model_id = os.getenv("HUNYUAN3D_MODEL_ID", "tencent/Hunyuan3D-2")
            logger.info(f"Loading pipeline weights from: {model_id}")
            self.paint_pipeline = Hunyuan3DPaintPipeline.from_pretrained(model_id)
            self.paint_pipeline = self.paint_pipeline.to(self.device)
            self.is_mock = False
            logger.info("Hunyuan3D-Paint model loaded successfully!")
        except ImportError as e:
            logger.warning(f"hy3dgen library is not installed or not compiled: {e}. Falling back to Mock Mode.")
            self.is_mock = True
        except Exception as e:
            logger.error(f"Failed to load Hunyuan3D-Paint model due to unexpected error: {e}. Falling back to Mock Mode.")
            self.is_mock = True

    def paint_mesh(self, mesh, image, **kwargs):
        """
        Textures an input trimesh using the loaded Hunyuan3D-Paint model.
        """
        if self.is_mock or self.paint_pipeline is None:
            raise RuntimeError("Hunyuan3D-Paint model is not loaded. Current state is Mock Mode.")
        
        # The pipeline accepts a trimesh.Trimesh object and a PIL Image
        # Returns a textured trimesh object
        logger.info("Running texture generation on the input mesh...")
        return self.paint_pipeline(mesh, image=image, **kwargs)

# Global model loader instance
model_loader = ModelLoader()
