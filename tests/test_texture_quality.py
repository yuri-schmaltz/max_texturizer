import sys
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from reference_images import pattern_image, pattern_kind
from texture_utils import apply_pattern, extract_albedo, neutral_maps


class TextureQualityTests(unittest.TestCase):
    def test_checker_obeys_both_requested_colors_and_typo(self):
        image = pattern_image('xadrex preto e amarelo', 512)
        pixels = np.asarray(image)
        self.assertGreater(np.mean(np.max(pixels, axis=2) < 30), .4)
        self.assertGreater(np.mean(np.max(np.abs(pixels.astype(int) - (255,210,0)), axis=2) < 15), .4)
        self.assertEqual(pattern_kind('xadrez'), 'checker')

    def test_red_dots_on_white_in_both_word_orders(self):
        for prompt in ('bolinhas vermelhas em fundo branco', 'fundo branco com bolinhas vermelhas'):
            with self.subTest(prompt=prompt):
                pixels = np.asarray(pattern_image(prompt, 512))
                self.assertGreater(np.mean(np.all(pixels == (250,250,250), axis=2)), .7)
                self.assertGreater(np.mean(np.max(np.abs(pixels.astype(int) - (220,20,30)), axis=2) < 15), .1)

    def test_preserve_existing_uv_and_geometry(self):
        mesh = trimesh.Trimesh(vertices=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]], faces=[[0,1,2],[0,2,3]], process=False)
        uv = np.array([[0,0],[1,0],[1,1],[0,1]], dtype=float)
        mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv)
        vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
        image = pattern_image('xadrez preto e amarelo', 128)
        result = apply_pattern(mesh, image, True)
        np.testing.assert_array_equal(result.vertices, vertices)
        np.testing.assert_array_equal(result.faces, faces)
        np.testing.assert_array_equal(result.visual.uv, uv)
        self.assertEqual(extract_albedo(result).tobytes(), image.tobytes())

    def test_invalid_uv_rejected_and_missing_texture_not_replaced_with_gray(self):
        with self.assertRaisesRegex(ValueError, 'UVs'):
            apply_pattern(trimesh.creation.box(), Image.new('RGB', (128,128)), True)
        with self.assertRaisesRegex(ValueError, 'mapa de cor'):
            extract_albedo(trimesh.creation.box())

    def test_auxiliary_maps_are_neutral_without_artificial_checker_bumps(self):
        roughness, normal = neutral_maps(128)
        self.assertEqual(roughness.getextrema(), (153,153))
        self.assertEqual(normal.getextrema(), ((128,128),(128,128),(255,255)))


if __name__ == '__main__':
    unittest.main()
