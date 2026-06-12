import os
import logging
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger("max-texturizer-backend")

def generate_procedural_textures(prompt, ref_image=None, resolution=1024):
    """
    Generates Albedo, Roughness, and Normal maps procedurally based on a prompt or reference image.
    """
    # Default Base Color (metallic gray)
    base_color = [180, 180, 185]
    roughness_val = 128
    is_metallic = False
    
    prompt_lower = prompt.lower() if prompt else ""
    
    # Determine material type and colors
    if ref_image:
        try:
            # Sample dominant color by resizing to 1x1
            sampled = ref_image.resize((1, 1), Image.Resampling.LANCZOS)
            color = sampled.getpixel((0, 0))
            # Support both RGB and RGBA
            base_color = list(color[:3])
            logger.info(f"Sampled base color from reference image: {base_color}")
        except Exception as e:
            logger.warning(f"Could not sample color from reference image: {e}. Using defaults.")

    elif "wood" in prompt_lower or "madeira" in prompt_lower or "tree" in prompt_lower:
        base_color = [115, 60, 20] # brown wood
        roughness_val = 180
    elif "gold" in prompt_lower or "ouro" in prompt_lower or "golden" in prompt_lower:
        base_color = [240, 190, 40] # gold
        roughness_val = 45
        is_metallic = True
    elif "metal" in prompt_lower or "iron" in prompt_lower or "ferro" in prompt_lower or "steel" in prompt_lower:
        base_color = [155, 155, 160] # metal
        roughness_val = 70
        is_metallic = True
    elif "grass" in prompt_lower or "grama" in prompt_lower or "green" in prompt_lower or "foliage" in prompt_lower:
        base_color = [45, 130, 45] # green
        roughness_val = 210
    elif "brick" in prompt_lower or "tijolo" in prompt_lower or "wall" in prompt_lower:
        base_color = [160, 50, 40] # brick red
        roughness_val = 220
    elif "water" in prompt_lower or "agua" in prompt_lower or "blue" in prompt_lower:
        base_color = [30, 110, 180] # blue water
        roughness_val = 30
    elif "sand" in prompt_lower or "areia" in prompt_lower:
        base_color = [210, 185, 130] # sandy yellow
        roughness_val = 240

    # 1. Albedo (Base Color) Map
    albedo = Image.new("RGB", (resolution, resolution), tuple(base_color))
    draw = ImageDraw.Draw(albedo)
    
    # Draw a checkerboard pattern combined with a simple gradient to show UV alignment
    squares = 16
    sq_size = resolution // squares
    for i in range(squares):
        for j in range(squares):
            if (i + j) % 2 == 0:
                # Make it slightly darker/lighter
                factor = 0.85 if (i + j) % 4 == 0 else 0.90
                c = [int(np.clip(val * factor, 0, 255)) for val in base_color]
                draw.rectangle(
                    [i * sq_size, j * sq_size, (i + 1) * sq_size, (j + 1) * sq_size],
                    fill=tuple(c)
                )
                
    # Add a visual "M" logo or text indicator to show it's mock
    try:
        draw.text((10, 10), "MOCK TEXTURE", fill=(255, 255, 255, 128))
    except Exception:
        pass

    # 2. Roughness Map (grayscale, representing surface roughness)
    roughness = Image.new("L", (resolution, resolution), roughness_val)
    r_draw = ImageDraw.Draw(roughness)
    for i in range(squares):
        for j in range(squares):
            if (i + j) % 2 == 0:
                r_draw.rectangle(
                    [i * sq_size, j * sq_size, (i + 1) * sq_size, (j + 1) * sq_size],
                    fill=int(np.clip(roughness_val * 1.15, 0, 255))
                )

    # 3. Normal Map (tangent space normal, base pointing straight out is RGB 128,128,255)
    normal = Image.new("RGB", (resolution, resolution), (128, 128, 255))
    n_draw = ImageDraw.Draw(normal)
    # Add simple bevel boundaries to make it look bumpy
    for i in range(squares):
        for j in range(squares):
            if (i + j) % 2 == 0:
                # Add light bumps: red channel represents X (-1 to +1 -> 0 to 255), green Y, blue Z
                n_draw.rectangle(
                    [i * sq_size + 2, j * sq_size + 2, (i + 1) * sq_size - 2, (j + 1) * sq_size - 2],
                    fill=(135, 135, 255) # slight normal skew
                )

    # Apply minor blur to normal and roughness for smoother look
    normal = normal.filter(ImageFilter.GaussianBlur(1))
    roughness = roughness.filter(ImageFilter.GaussianBlur(1))

    return albedo, roughness, normal


def apply_mock_texture_to_mesh(mesh_path, prompt, ref_image=None, resolution=1024):
    """
    Loads a mesh file, generates mock textures, builds UVs if missing,
    applies the simple PBR texture material to the mesh, and returns it.
    """
    logger.info(f"Loading mesh for mock texturing from: {mesh_path}")
    mesh = trimesh.load(mesh_path, force='mesh')
    
    # 1. Unwrapping check
    if not hasattr(mesh.visual, 'uv') or mesh.visual.uv is None or len(mesh.visual.uv) == 0:
        logger.info("No UV coordinates found on input mesh. Generating simple box projection mapping.")
        vertices = mesh.vertices
        if len(vertices) > 0:
            # Normalize vertices between 0 and 1 for simple projection mapping
            min_coords = vertices.min(axis=0)
            max_coords = vertices.max(axis=0)
            range_coords = max_coords - min_coords
            range_coords[range_coords == 0] = 1e-5
            
            normalized = (vertices - min_coords) / range_coords
            # Simple X-Y projection mapping
            u = normalized[:, 0]
            v = normalized[:, 1]
            mesh.visual.uv = np.stack([u, v], axis=1)
        else:
            mesh.visual.uv = np.zeros((0, 2))

    # 2. Generate procedural textures
    albedo, roughness, normal = generate_procedural_textures(prompt, ref_image, resolution)

    # 3. Create simple material for the mesh
    # trimesh GLTF exporter reads SimpleMaterial and embeds the image as a baseColorTexture
    material = trimesh.visual.texture.SimpleMaterial(
        image=albedo,
        roughness=0.5 if ref_image else (0.8 if "wood" in prompt.lower() else 0.2)
    )
    mesh.visual.material = material

    return mesh, albedo, roughness, normal
