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

    auto_start_backend: bpy.props.BoolProperty(
        name="Iniciar backend automaticamente",
        description="Inicia o servidor local em segundo plano ao ativar o add-on",
        default=True,
    )

    backend_directory: bpy.props.StringProperty(
        name="Pasta do projeto",
        description="Pasta que contém run_backend.sh; deixe vazio para usar o caminho registrado no ZIP",
        subtype='DIR_PATH',
        default="",
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
        column.prop(self, "auto_start_backend")
        column.prop(self, "backend_directory")
        column.operator("object.max_texturizer_start_backend", icon='PLAY')
        
        column.separator()
        column.label(text="Configurações do LLM Local:")
        column.prop(self, "llm_url")
        column.prop(self, "llm_model")

def register():
    bpy.utils.register_class(MaxTexturizerPreferences)

def unregister():
    bpy.utils.unregister_class(MaxTexturizerPreferences)
