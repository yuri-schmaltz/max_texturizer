"""Loader regressions without downloading model weights or requiring a GPU."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True))
        spec = importlib.util.spec_from_file_location(
            "loader_under_test", Path(__file__).resolve().parents[1] / "backend/model_loader.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"torch": self.torch}):
            spec.loader.exec_module(self.module)
        self.loader = self.module.ModelLoader()

    def test_real_wrapper_has_no_to_and_accepts_only_mesh_image(self):
        class Pipeline:
            offloaded = False

            @classmethod
            def from_pretrained(cls, model_id):
                return cls()

            def enable_model_cpu_offload(self):
                self.offloaded = True

            def __call__(self, mesh, image):
                return mesh, image

        texgen = types.ModuleType("hy3dgen.texgen")
        texgen.Hunyuan3DPaintPipeline = Pipeline
        with patch.dict(sys.modules, {"hy3dgen": types.ModuleType("hy3dgen"), "hy3dgen.texgen": texgen}):
            self.loader.load_models(require_real=True)
        self.assertFalse(self.loader.is_mock)
        self.assertTrue(self.loader.paint_pipeline.offloaded)
        self.assertEqual(self.loader.paint_mesh("mesh", "image", steps=20, guidance_scale=7.5), ("mesh", "image"))

    def test_missing_hy3dgen_is_fatal_when_real_required(self):
        with patch.dict(sys.modules, {"hy3dgen": None}):
            with self.assertRaisesRegex(RuntimeError, "run_backend.sh --real"):
                self.loader.load_models(require_real=True)
        self.assertTrue(self.loader.is_mock)
        self.assertIsNotNone(self.loader.load_error)

    def test_preserved_uv_skips_only_unwrap_and_restores_it_after_failure(self):
        wrapper = types.ModuleType('test_paint_wrapper')
        original_unwrap = lambda mesh: 'changed'
        wrapper.mesh_uv_wrap = original_unwrap
        validation = types.SimpleNamespace(validate_preserved_uv=lambda mesh: None)

        class Pipeline:
            __module__ = 'test_paint_wrapper'
            fail = False
            config = types.SimpleNamespace(texture_size=2048)
            render = types.SimpleNamespace(set_default_texture_resolution=lambda size: None)

            def __call__(self, mesh, image):
                self.assert_preserved = wrapper.mesh_uv_wrap(mesh) is mesh
                if self.fail:
                    raise ValueError('render failed')
                return mesh

        self.loader.paint_pipeline = Pipeline()
        self.loader.is_mock = False
        mesh = object()
        with patch.dict(sys.modules, {'test_paint_wrapper': wrapper, 'texture_utils': validation}):
            self.assertIs(self.loader.paint_mesh(mesh, None, preserve_uv=True, resolution=512), mesh)
            self.assertTrue(self.loader.paint_pipeline.assert_preserved)
            self.assertEqual(self.loader.paint_pipeline.config.texture_size, 512)
            self.assertIs(wrapper.mesh_uv_wrap, original_unwrap)
            self.loader.paint_pipeline.fail = True
            with self.assertRaisesRegex(ValueError, 'render failed'):
                self.loader.paint_mesh(mesh, None, preserve_uv=True)
            self.assertIs(wrapper.mesh_uv_wrap, original_unwrap)

    def test_missing_cuda_is_fatal_when_real_required(self):
        with patch.object(self.module, "torch", None):
            with self.assertRaisesRegex(RuntimeError, "CUDA"):
                self.loader.load_models(require_real=True)

    def test_auto_fallback_exposes_reason(self):
        with patch.dict(sys.modules, {"hy3dgen": None}):
            self.loader.load_models()
        self.assertTrue(self.loader.is_mock)
        self.assertIn("hy3dgen", self.loader.load_error)

    def test_explicit_mock_does_not_require_torch(self):
        with patch.object(self.module, "torch", None):
            self.loader.load_models(force_mock=True)
        self.assertTrue(self.loader.is_mock)
        self.assertIsNone(self.loader.load_error)


if __name__ == "__main__":
    unittest.main()
