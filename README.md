# Max Texturizer IA 🎨🤖

[![Latest Release](https://img.shields.io/github/v/release/yuri-schmaltz/my-texturizer?include_prereleases&style=flat-square)](https://github.com/yuri-schmaltz/my-texturizer/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Blender 3.3+](https://img.shields.io/badge/Blender-3.3%2B-orange.svg?style=flat-square)](https://www.blender.org/)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg?style=flat-square)](https://www.python.org/)

**Max Texturizer** é um ecossistema para automatizar a geração e aplicação de texturas 3D realistas em malhas (meshes) no **Blender** usando Inteligência Artificial (**Hunyuan3D-Paint**). O sistema é dividido em duas partes:

1. **Backend FastAPI** — servidor local que gerencia modelos de IA, gera imagens-guia e executa a texturização. Suporta **Modo Mock** (texturas procedurais instantâneas, sem GPU) e **Modo Real** (Hunyuan3D-Paint, requer GPU NVIDIA + CUDA).
2. **Blender Add-on** — painel na barra lateral (N-Panel) do Blender 3D para configurar parâmetros, exportar o modelo, enviar para o backend e reintegrar o resultado automaticamente.

> **Status atual:** Modo Mock e o orquestrador LLM são funcionais e testados. O Modo Real (Hunyuan3D-Paint) requer configuração manual de CUDA + `hy3dgen` (veja [Modo Real](#-modo-real-com-gpu)).

---

## 🛠️ Arquitetura

```
┌──────────────────┐         HTTP / JSON          ┌─────────────────────┐
│   Blender 3D     │  ◄────────────────────────►   │   FastAPI Backend   │
│   (N-Panel)      │      GLB + textura           │   (porta 8009)      │
│                  │                                │                     │
│  • Export mesh   │                                │  /health            │
│  • Apply PBR     │                                │  /generate-ref-image│
│  • Orchestrate   │                                │  /texture           │
└──────────────────┘                                │  /orchestrate       │
                                                    └──────────┬──────────┘
                                                               │
                                          ┌────────────────────┴──────────┐
                                          │                                │
                                  Modo Mock (CPU)              Modo Real (GPU)
                                  ─────────────────            ───────────────
                                  • PIL + NumPy                 • Hunyuan3D-Paint
                                  • Padrões procedurais         • hy3dgen + PyTorch
                                  • xadrez + gradiente          • tencent/Hunyuan3D-2
                                  • PBR maps sintéticos         • PBR maps neurais
```

O add-on também se integra opcionalmente a um **LLM local** (Ollama, LM Studio ou qualquer endpoint OpenAI-compatible) para orquestração inteligente de propriedades PBR por slot de material.

---

## 📋 Pré-requisitos

- **Python 3.9+**
- **Blender 3.3+**
- **Para Modo Real:** GPU NVIDIA com CUDA 11.8+ e 8 GB+ VRAM
- **Para Orquestração LLM (opcional):** [Ollama](https://ollama.com) rodando localmente (`ollama serve`) com um modelo instalado (ex: `ollama pull llama3`)

---

## 🚀 Instalação e Execução

### 1. Iniciar o Backend

Na raiz do projeto, execute:

```bash
./run_backend.sh
```

O script automaticamente:

1. Cria um ambiente virtual Python em `backend/venv/`
2. Instala as dependências de `backend/requirements.txt`
3. Inicia o servidor em `http://127.0.0.1:8009`

Acesse a documentação interativa (Swagger UI):
👉 [http://127.0.0.1:8009/docs](http://127.0.0.1:8009/docs)

### 2. Instalar o Add-on no Blender

```bash
# Empacotar a pasta do add-on em um ZIP
zip -r max_texturizer.zip blender_addon
```

1. Abra o **Blender 3.3+**
2. Vá em **Edit → Preferences → Add-ons**
3. Clique em **Install...** e selecione `max_texturizer.zip`
4. Ative **3D View: Max Texturizer IA**
5. (Opcional) Expanda as preferências do add-on para ajustar a URL do backend (padrão: `http://127.0.0.1:8009`)

---

## 🎮 Como Usar

Abra o painel lateral do Blender com **N** na Viewport 3D e selecione a aba **Max Texturizer**.

### A. Texturização de Mesh (básico)

1. **Verificar Conexão** — confirma que o add-on alcança o backend. Exibe o modo ativo (Mock/Real) e o dispositivo (CPU/CUDA).
2. **Configurar Prompt** — descreva a textura desejada (ex: `madeira rústica de carvalho, veios escuros`). Preencha também o **Prompt Negativo** (ex: `distorcido, baixa resolução`).
3. **Escolher o Método de Integração:**
   - **Mapear UVs Existentes** *(padrão)* — mantém sua geometria e aplica as texturas geradas diretamente nas UVs do objeto.
   - **Substituir por Malha .glb** — substitui o objeto por uma nova malha importada com UVs otimizadas pela IA.
4. **Visualizar Imagem de Referência** — gera uma imagem preliminar para você inspecionar antes de texturizar. A imagem aparece no Editor de Imagens do Blender como `MaxTexturizer_Preview`.
5. **Gerar Textura** — exporta o mesh, envia para o backend e aplica o resultado automaticamente.

### B. Orquestração PBR com LLM (avançado)

Para configurar shaders procedurais (edge wear, scratches, dirt) nos slots de material do objeto via LLM local:

1. Selecione um objeto com **múltiplos slots de material**
2. Preencha o **Prompt** descrevendo o objeto (ex: `espada medieval desgastada, lâmina de aço, cabo de couro`)
3. Certifique-se de que o Ollama está rodando (padrão: `http://localhost:11434`, modelo: `llama3`)
4. Clique em **Orquestrar com LLM**

O backend envia a descrição + lista de slots para o LLM, que retorna propriedades PBR e flags de efeitos procedurais. O add-on monta automaticamente o node tree no Blender para cada slot.

> **Fallback offline:** se o LLM estiver indisponível, o backend usa um parser de keywords que reconhece materiais comuns (metal, madeira, couro, etc.).

---

## 💡 Modo Mock vs Modo Real (Hunyuan3D-Paint)

| | **Modo Mock** (padrão) | **Modo Real** (Hunyuan3D) |
|---|---|---|
| **GPU necessária** | ❌ Não | ✅ NVIDIA + CUDA |
| **Velocidade** | Instantâneo (~100ms) | Minutos por textura |
| **Qualidade** | Padrões procedurais simples | PBR neural realista |
| **Ativação** | Automática (sem CUDA) ou `FORCE_MOCK=true` | CUDA + `hy3dgen` instalado |

### Ativar o Modo Real

1. Instale o PyTorch com suporte CUDA:
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu118
   ```
2. Instale o `hy3dgen` (requer compilação — veja o [repositório oficial](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)):
   ```bash
   pip install hy3dgen
   ```
3. O backend baixará automaticamente os pesos do `tencent/Hunyuan3D-2` do Hugging Face na primeira execução.
4. Verifique o modo ativo em **Verificar Conexão** no painel do Blender.

Para forçar o Modo Mock mesmo com GPU disponível:
```bash
FORCE_MOCK=true ./run_backend.sh
```
Ou marque **Forçar Modo Mock** nas preferências do add-on.

---

## 🔌 Endpoints da API

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Status do servidor, modo ativo, dispositivo |
| `GET` | `/generate-ref-image?prompt=...` | Gera imagem de referência (PIL mock ou SD pública) |
| `POST` | `/texture` | Recebe mesh + prompt, retorna ZIP com `mesh.glb`, `albedo.png`, `roughness.png`, `normal.png` |
| `POST` | `/orchestrate` | Recebe prompt + slots, retorna JSON com PBR e flags de efeitos procedurais |

---

## 🧩 Integração Opcional: Fluent Materializer

O orquestrador detecta automaticamente **node groups** nomeados com `edge_wear` ou `fluent_edge` no `.blend` ativo e os usa em vez do fallback nativo (Pointiness + Noise). Se você tem o [Fluent Materializer](https://gumroad.com/l/fluent-materializer) instalado e um .blend aberto com esses node groups, a orquestração automaticamente os utiliza.

> O Fluent Materializer **não é distribuído junto** com este projeto. Instale-o separadamente se quiser esse comportamento.

---

## 📁 Estrutura do Projeto

```
my-texturizer/
├── backend/                  # Servidor FastAPI
│   ├── main.py               # Endpoints REST
│   ├── mock_generator.py     # Geração procedural (PBR mock)
│   ├── model_loader.py       # Carregamento do Hunyuan3D-Paint
│   ├── llm_orchestrator.py   # Integração com LLM local (Ollama)
│   └── requirements.txt
├── blender_addon/            # Add-on Blender (N-Panel)
│   ├── __init__.py
│   ├── addon_preferences.py
│   ├── operators.py
│   └── ui.py
├── run_backend.sh            # Script de inicialização
├── README.md
├── LICENSE                   # MIT
└── .gitignore
```

---

## 🛣️ Roadmap

- [ ] Substituir dependência de API pública (Pollinations.ai) por modelo local leve (SD-Turbo / SDXL-Lightning)
- [ ] Testes automatizados para `mock_generator` e `llm_orchestrator` (funções puras, cobertura fácil)
- [ ] Documentação de setup CUDA/hy3dgen validada em GPU real
- [ ] CI/CD com GitHub Actions (lint + smoke tests)
- [ ] Suporte a múltiplos mapas PBR (metallic, AO, displacement)

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE).
