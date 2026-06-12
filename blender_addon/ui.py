import bpy

class VIEW3D_PT_MaxTexturizer(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Max Texturizer'
    bl_label = 'Max Texturizer IA'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 1. Connection Section
        row = layout.row()
        row.scale_y = 1.1
        row.operator("object.max_texturizer_check_connection", icon='WORLD')

        layout.separator()

        # 2. Prompts Configuration
        box_prompt = layout.box()
        box_prompt.label(text="Instruções de Textura", icon='TEXT')
        box_prompt.prop(scene, "max_texturizer_prompt", text="Prompt")
        box_prompt.prop(scene, "max_texturizer_neg_prompt", text="Negativo")

        # 3. Parameters Selection
        box_params = layout.box()
        box_params.label(text="Configurações da Geração", icon='PREFERENCES')
        box_params.prop(scene, "max_texturizer_resolution", text="Resolução")
        box_params.prop(scene, "max_texturizer_steps", text="Passos IA")
        box_params.prop(scene, "max_texturizer_guidance", text="Guidance Scale")

        # 4. Import / Apply configuration
        box_integ = layout.box()
        box_integ.label(text="Aplicar na Scene", icon='OUTLINER_OB_MESH')
        box_integ.prop(scene, "max_texturizer_mode", expand=True)

        layout.separator()

        # 5. Core Actions
        col_actions = layout.column(align=True)
        col_actions.scale_y = 1.2
        col_actions.operator("object.max_texturizer_preview", icon='IMAGE_DATA')
        
        col_actions.separator()
        
        col_generate = col_actions.column()
        col_generate.scale_y = 1.5
        col_generate.operator("object.max_texturizer_generate", icon='MATERIAL')

        # 6. Informative box if preview image is present in file data
        if "MaxTexturizer_Preview" in bpy.data.images:
            layout.separator()
            box_info = layout.box()
            box_info.label(text="Imagem Guia Disponível", icon='CHECKMARK')
            box_info.label(text="Para ver a imagem:")
            box_info.label(text="Abra o editor de imagens e")
            box_info.label(text="selecione 'MaxTexturizer_Preview'")
            
def register():
    bpy.utils.register_class(VIEW3D_PT_MaxTexturizer)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_MaxTexturizer)
