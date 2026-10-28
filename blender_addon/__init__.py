bl_info = {
    "name": "Max Texturizer IA",
    "author": "Antigravity",
    "version": (1, 3, 1),
    "blender": (3, 3, 0),
    "location": "View3D > Sidebar > Max Texturizer",
    "description": "Texturização automática de malhas 3D usando inteligência artificial (Hunyuan3D-Paint)",
    "category": "3D View",
}

# Reload modules if already loaded to support quick development in Blender
if "addon_preferences" in locals():
    import importlib
    importlib.reload(addon_preferences)
    importlib.reload(operators)
    importlib.reload(ui)

import bpy
from . import addon_preferences
from . import operators
from . import ui

def register():
    # 1. Register properties on the Scene
    bpy.types.Scene.max_texturizer_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="Prompt de texto para descrever a aparência da textura",
        default="madeira envelhecida, detalhes realistas, 4k"
    )
    
    bpy.types.Scene.max_texturizer_neg_prompt = bpy.props.StringProperty(
        name="Prompt Negativo",
        description="Elementos que devem ser evitados na geração",
        default="distorcido, baixa resolução, ruído, desenho animado"
    )
    
    bpy.types.Scene.max_texturizer_resolution = bpy.props.EnumProperty(
        name="Resolução",
        description="Resolução dos mapas de textura gerados",
        items=[
            ('512', '512x512', 'Processamento rápido, qualidade padrão'),
            ('1024', '1024x1024', 'Alta resolução recomendada'),
            ('2048', '2048x2048', 'Ultra qualidade, requer mais VRAM')
        ],
        default='1024'
    )
    
    bpy.types.Scene.max_texturizer_steps = bpy.props.IntProperty(
        name="Passos de Inferência",
        description="Número de passos do pipeline de difusão (quanto maior, mais detalhes)",
        default=20,
        min=1,
        max=100
    )
    
    bpy.types.Scene.max_texturizer_guidance = bpy.props.FloatProperty(
        name="Guidance Scale",
        description="Adesão ao prompt vs criatividade (valores típicos entre 5.0 e 12.0)",
        default=7.5,
        min=1.0,
        max=20.0
    )
    
    bpy.types.Scene.max_texturizer_mode = bpy.props.EnumProperty(
        name="Método de Integração",
        description="Escolha como a textura gerada será aplicada",
        items=[
            ('IMPORT_GLB', 'Substituir por Malha .glb', 'Importa um novo modelo com UVs otimizadas geradas pela IA'),
            ('APPLY_MATERIAL', 'Mapear UVs Existentes', 'Mantém a geometria original e apenas aplica as novas texturas na UV atual')
        ],
        default='APPLY_MATERIAL'
    )
    
    # 2. Register Submodules
    addon_preferences.register()
    operators.register()
    ui.register()

def unregister():
    # 1. Clean properties
    del bpy.types.Scene.max_texturizer_prompt
    del bpy.types.Scene.max_texturizer_neg_prompt
    del bpy.types.Scene.max_texturizer_resolution
    del bpy.types.Scene.max_texturizer_steps
    del bpy.types.Scene.max_texturizer_guidance
    del bpy.types.Scene.max_texturizer_mode

    # 2. Unregister Submodules
    addon_preferences.unregister()
    operators.unregister()
    ui.unregister()

if __name__ == "__main__":
    register()
