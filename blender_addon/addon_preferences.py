import bpy

class MaxTexturizerPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__ if __package__ else "blender_addon"

    server_url: bpy.props.StringProperty(
        name="Endereço do Servidor",
        description="URL do servidor FastAPI local",
        default="http://127.0.0.1:8009",
    )

    force_mock: bpy.props.BoolProperty(
        name="Forçar Modo Mock",
        description="Força o servidor a usar o gerador procedimental mesmo se CUDA estiver disponível",
        default=False,
    )

    llm_url: bpy.props.StringProperty(
        name="Ollama/LM Studio URL",
        description="Endereço da API do LLM local",
        default="http://localhost:11434",
    )

    llm_model: bpy.props.StringProperty(
        name="Modelo do LLM",
        description="Nome do modelo local instalado (ex: llama3, qwen2.5, mistral)",
        default="llama3",
    )

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        column.label(text="Configurações do Servidor de Imagem/3D:")
        column.prop(self, "server_url")
        column.prop(self, "force_mock")
        
        column.separator()
        column.label(text="Configurações do LLM Local:")
        column.prop(self, "llm_url")
        column.prop(self, "llm_model")

def register():
    bpy.utils.register_class(MaxTexturizerPreferences)

def unregister():
    bpy.utils.unregister_class(MaxTexturizerPreferences)
