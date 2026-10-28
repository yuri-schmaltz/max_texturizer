# Max Texturizer IA 🎨🤖

[![Latest Release](https://img.shields.io/github/v/release/yuri-schmaltz/my-texturizer?include_prereleases&style=flat-square)](https://github.com/yuri-schmaltz/my-texturizer/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Blender 3.3+](https://img.shields.io/badge/Blender-3.3%2B-orange.svg?style=flat-square)](https://www.blender.org/)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg?style=flat-square)](https://www.python.org/)

**Max Texturizer** é um ecossistema para automatizar a geração e aplicação de texturas 3D realistas em malhas (meshes) no **Blender** usando Inteligência Artificial (**Hunyuan3D-Paint**). O sistema é dividido em duas partes:

1. **Backend FastAPI** — servidor local que gerencia modelos de IA, gera imagens-guia e executa a texturização. Suporta **Modo Mock** (texturas procedurais instantâneas, sem GPU) e **Modo Real** (Hunyuan3D-Paint, requer GPU NVIDIA + CUDA).
2. **Blender Add-on** — painel na barra lateral (N-Panel) do Blender 3D para configurar parâmetros, exportar o modelo, enviar para o backend e reintegrar o resultado automaticamente.

> **Status atual:** Modo Mock e o orquestrador LLM são funcionais e testados. O Modo Real (Hunyuan3D-Paint) instala `hy3dgen` e compila suas extensões automaticamente; requer driver NVIDIA, CUDA Toolkit 12.x, Git e compilador C++ (veja abaixo).

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
- **Para Modo Real:** GPU NVIDIA, driver compatível com CUDA 12.4, CUDA Toolkit 12.x (`nvcc`), Git e compilador C++. A memória necessária varia com a malha; o carregador habilita CPU offload por padrão.
- **Para Orquestração LLM (opcional):** [Ollama](https://ollama.com) rodando localmente (`ollama serve`) com um modelo instalado (ex: `ollama pull llama3`)

---

## 🚀 Instalação e Execução

### 1. Manter o projeto disponível

Mantenha a pasta deste projeto no computador: o add-on usa os scripts e o ambiente Python dessa pasta. Ao ativar o add-on, ele inicia o backend automaticamente em segundo plano.

Para iniciar pelo terminal, opcionalmente execute:

```bash
./run_backend.sh
```

O script automaticamente:

1. Cria um ambiente virtual Python em `backend/venv/`
2. Detecta GPU NVIDIA: prepara o modo real quando disponível; usa Mock em máquinas sem GPU
3. No modo real, instala PyTorch CUDA, as dependências de inferência, `hy3dgen` de uma revisão fixa e compila as duas extensões
4. Carrega os pesos e inicia o servidor em `http://127.0.0.1:8009`

Use `./run_backend.sh --real` ou `./run_backend.sh --mock` para escolher explicitamente. Se a preparação ou o carregamento do modo real falhar, a inicialização para com o erro, sem trocar automaticamente para Mock. A primeira execução pode demorar e baixar vários GB de dependências e pesos.

Se já houver um Max Texturizer saudável no mesmo endereço e modo, o script informa que ele está disponível e termina sem carregar outro modelo. Se a porta estiver ocupada por outro serviço ou modo, ele avisa antes da instalação. Use `PORT=8010 ./run_backend.sh --real` para iniciar em outra porta e configure a mesma porta no add-on.

Acesse a documentação interativa (Swagger UI):
👉 [http://127.0.0.1:8009/docs](http://127.0.0.1:8009/docs)

### 2. Instalar o Add-on no Blender

```bash
# Gerar o ZIP com o caminho do backend desta cópia do projeto
python3 package_addon.py
```

1. Abra o **Blender 3.3+**
2. Vá em **Edit → Preferences → Add-ons**
3. Clique em **Install...** e selecione `max_texturizer.zip`
4. Ative **3D View: Max Texturizer IA**
5. Aguarde o painel indicar **Conectado: Hunyuan3D / CUDA**. O backend é iniciado automaticamente; nenhum terminal precisa ficar aberto.
6. Nas preferências, mantenha **Iniciar backend automaticamente** ativado e a URL `http://127.0.0.1:8009`. O ZIP já registra a pasta do projeto. Se mover o projeto ou usar outro computador, indique a nova **Pasta do projeto**, que contém `run_backend.sh`, ou gere um novo ZIP.

O painel oferece **Iniciar Backend**, **Verificar Conexão** e **Abrir log do backend**. A instalação das dependências e o carregamento dos pesos acontecem em segundo plano; as ações de geração ficam indisponíveis durante essa preparação. Falhas aparecem no painel e o log fica em `~/.cache/max-texturizer/backend.log`. Um servidor já ativo é reutilizado. O backend continua rodando ao fechar o Blender ou desativar o add-on.

**Blender via Flatpak:** o add-on usa `flatpak-spawn --host` para iniciar o Python e o CUDA do sistema. A instalação Flatpak precisa desta permissão, configurada uma vez no terminal do sistema:

```bash
flatpak override --user --talk-name=org.freedesktop.Flatpak org.blender.Blender
```

Reabra o Blender após mudar a permissão. Ela já foi configurada nesta máquina. A inicialização local aceita URLs HTTP de `localhost`, `127.0.0.1` e `::1`; servidores remotos precisam ser iniciados na própria máquina remota.

---

## 🎮 Como Usar

Abra o painel lateral do Blender com **N** na Viewport 3D e selecione a aba **Max Texturizer**.

### A. Texturização de Mesh (básico)

1. **Verificar Conexão** — verifica o backend em segundo plano e, se a inicialização automática estiver ativa, inicia o servidor caso necessário. O estado aparece no painel.
2. **Configurar Prompt** — descreva a textura desejada (ex: `madeira rústica de carvalho, veios escuros`). Preencha também o **Prompt Negativo** (ex: `distorcido, baixa resolução`).
3. **Escolher o Método de Integração:**
   - **Mapear UVs Existentes** *(padrão)* — mantém sua geometria e aplica as texturas geradas diretamente nas UVs do objeto.
   - **Substituir por Malha .glb** — substitui o objeto por uma nova malha importada com UVs otimizadas pela IA.
4. **Visualizar Imagem de Referência** — gera uma imagem preliminar para você inspecionar antes de texturizar. A imagem aparece no Editor de Imagens do Blender como `MaxTexturizer_Preview`.
5. **Gerar Textura** — exporta o mesh, envia para o backend e aplica o resultado automaticamente. Após aplicar ou atualizar a textura, o add-on atualiza as imagens, os materiais e a viewport. Visualizações em Sólido/Aramado passam para Material Preview; Rendered permanece em Rendered.

### B. Orquestração PBR com LLM (avançado)

Para configurar shaders procedurais (edge wear, scratches, dirt) nos slots de material do objeto via LLM local:

1. Selecione um objeto com **múltiplos slots de material**
2. Preencha o **Prompt** descrevendo o objeto (ex: `espada medieval desgastada, lâmina de aço, cabo de couro`)
3. Certifique-se de que o Ollama está rodando (padrão: `http://localhost:11434`, modelo: `llama3`)
4. Nas preferências do add-on, confira a URL do LLM e escolha o **Modelo do LLM** na lista de modelos disponíveis. A busca ocorre ao abrir o Blender e ao alterar a URL; use o ícone de atualização para buscar novamente. O nome exato selecionado é enviado ao orquestrador.
5. Clique em **Orquestrar com LLM**

O backend envia a descrição + lista de slots para o LLM, que retorna propriedades PBR e flags de efeitos procedurais. O add-on monta automaticamente o node tree no Blender para cada slot.

A lista consulta `/api/tags` no Ollama e `/v1/models` em servidores compatíveis, como LM Studio. URLs terminadas em `/v1` também são aceitas. Se precisar digitar um identificador, ative **Informar modelo manualmente**. Uma seleção anterior é preservada e marcada como **atual; não listado** quando não aparece no servidor; escolha um modelo listado antes de orquestrar.

> **Fallback offline:** se o LLM estiver indisponível, o backend usa um parser de keywords que reconhece materiais comuns (metal, madeira, couro, etc.).

---

## 💡 Modo Mock vs Modo Real (Hunyuan3D-Paint)

| | **Modo Mock** (padrão) | **Modo Real** (Hunyuan3D) |
|---|---|---|
| **GPU necessária** | ❌ Não | ✅ NVIDIA + CUDA |
| **Velocidade** | Instantâneo (~100ms) | Minutos por textura |
| **Qualidade** | Padrões procedurais simples | PBR neural realista |
| **Ativação** | Sem GPU ou `./run_backend.sh --mock` | Automática com GPU ou `./run_backend.sh --real` |

### Ativar o Modo Real

1. Verifique `nvidia-smi`, `nvcc --version`, `git --version` e `g++ --version`. O instalador usa PyTorch 2.6.0/cu124 e torchvision 0.21.0; o Toolkit deve ser da família CUDA 12. Em Ubuntu com CUDA 12.0, instale GCC/G++ 12 (o script os seleciona se disponíveis).
2. Na raiz **desta cópia do projeto**, execute:
   ```bash
   ./run_backend.sh --real
   ```
   O script instala a biblioteca do [repositório oficial](https://github.com/Tencent-Hunyuan/Hunyuan3D-2), compila `custom_rasterizer` e `mesh_processor` e verifica os imports no mesmo `backend/venv` usado pelo servidor. As dependências Python são restritas ao caminho de inferência de pintura; demos e geração de geometria não são instaladas.
3. Aguarde o download dos pesos de `tencent/Hunyuan3D-2` e o carregamento. O servidor só aceita conexões após essa etapa.
4. Consulte `http://127.0.0.1:8009/health`: o resultado deve conter `"is_mock": false` e `"load_error": null`.

Os fontes ficam em `backend/vendor/` (ignorado pelo Git); as próximas execuções reaproveitam a instalação. Para reinstalar as extensões, remova apenas `backend/vendor/Hunyuan3D-2/.texturizer-installed` e execute novamente.

O wrapper de pintura Hunyuan3D-2 recebe apenas a malha e a imagem. Os controles de steps, guidance e prompt negativo do add-on não são repassados a esse wrapper, que usa a configuração de amostragem do próprio Hunyuan. A geração da imagem de referência ainda depende do serviço externo descrito no roadmap.

O offload para RAM fica ativo por padrão para reduzir o uso de VRAM. Para desativá-lo, use `HUNYUAN3D_CPU_OFFLOAD=false ./run_backend.sh --real`. Para desenvolvimento com recarga automática, use `RELOAD=true` (os pesos serão recarregados a cada alteração).

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
