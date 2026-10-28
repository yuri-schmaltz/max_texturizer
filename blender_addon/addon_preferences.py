import bpy
import textwrap
from .llm_models import catalog

# Blender retains pointers to enum strings; keep these lists alive across redraws.
_model_items_cache = {}


def model_items(self, context):
    state = catalog.snapshot()
    names = state['models'] if state['url'] == self.llm_url.strip().rstrip('/') else ()
    key = (names, self.llm_model)
    if key not in _model_items_cache:
        items = [(name, name, 'Usar este modelo na orquestração de materiais', i) for i, name in enumerate(names)]
        if self.llm_model and self.llm_model not in names:
            items.append((self.llm_model, self.llm_model + ' (atual; não listado)', 'Modelo configurado anteriormente ou informado manualmente', len(items)))
        _model_items_cache[key] = items or [('__NONE__', 'Nenhum modelo disponível', 'Clique em Atualizar modelos', 0)]
    return _model_items_cache[key]


def selected_model_get(self):
    return next((item[3] for item in model_items(self, None) if item[0] == self.llm_model), 0)


def selected_model_set(self, value):
    for identifier, label, description, number in model_items(self, None):
        if number == value and identifier != '__NONE__':
            self.llm_model = identifier
            break


def llm_url_updated(self, context):
    catalog.refresh(self.llm_url)

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
        update=llm_url_updated,
    )

    llm_model: bpy.props.StringProperty(
        name="Modelo do LLM",
        description="Nome do modelo local instalado (ex: llama3, qwen2.5, mistral)",
        default="llama3",
    )

    llm_model_selection: bpy.props.EnumProperty(
        name="Modelo do LLM",
        description="Modelos disponíveis no servidor configurado",
        items=model_items,
        get=selected_model_get,
        set=selected_model_set,
    )

    llm_manual_model: bpy.props.BoolProperty(
        name="Informar modelo manualmente",
        default=False,
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
        state = catalog.snapshot()
        row = column.row(align=True)
        selector = row.row(align=True)
        selector.enabled = state['status'] != 'loading'
        selector.prop(self, "llm_model_selection")
        refresh = row.row(align=True)
        refresh.enabled = state['status'] != 'loading'
        refresh.operator("object.max_texturizer_refresh_models", text="", icon='FILE_REFRESH')
        for line in textwrap.wrap(state['message'], width=85):
            column.label(text=line, icon='ERROR' if state['status'] == 'error' else 'INFO')
        column.prop(self, "llm_manual_model")
        if self.llm_manual_model:
            column.prop(self, "llm_model", text="Nome do modelo")

def register():
    bpy.utils.register_class(MaxTexturizerPreferences)

def unregister():
    bpy.utils.unregister_class(MaxTexturizerPreferences)
