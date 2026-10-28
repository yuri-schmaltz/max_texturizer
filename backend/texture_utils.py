"""Keep UV layout and output maps consistent with the generated material."""
import numpy as np
import trimesh
from PIL import Image


def valid_uv(mesh):
    uv = getattr(mesh.visual, 'uv', None)
    return (uv is not None and np.shape(uv) == (len(mesh.vertices), 2)
            and np.isfinite(uv).all() and np.min(uv) >= -1e-5 and np.max(uv) <= 1.00001)


def validate_preserved_uv(mesh):
    if not valid_uv(mesh):
        raise ValueError('A malha precisa de UVs válidas dentro de 0–1 para Mapear UVs Existentes. Crie um UV unwrap no Blender ou use Substituir por Malha .glb.')


def neutral_maps(resolution):
    return Image.new('L', (resolution, resolution), 153), Image.new('RGB', (resolution, resolution), (128,128,255))


def apply_pattern(mesh, image, preserve_uv):
    if preserve_uv:
        validate_preserved_uv(mesh)
        uv = np.asarray(mesh.visual.uv).copy()
    else:
        import xatlas
        mapping, faces, uv = xatlas.parametrize(np.asarray(mesh.vertices, dtype=np.float32), np.asarray(mesh.faces, dtype=np.uint32))
        mesh = trimesh.Trimesh(vertices=mesh.vertices[mapping], faces=faces, process=False)
    mesh.visual = trimesh.visual.texture.TextureVisuals(
        uv=uv, material=trimesh.visual.material.PBRMaterial(baseColorTexture=image, metallicFactor=0.0, roughnessFactor=0.6))
    return mesh


def extract_albedo(mesh):
    material = getattr(mesh.visual, 'material', None)
    for name in ('baseColorTexture', 'image'):
        image = getattr(material, name, None)
        if isinstance(image, Image.Image):
            return image.convert('RGB')
    raise ValueError('O modelo não retornou um mapa de cor. A geração falhou; nenhuma textura cinza foi substituída no resultado.')
