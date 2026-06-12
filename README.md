# Max Texturizer IA 🎨🤖

**Max Texturizer** é um ecossistema projetado para automatizar a geração e aplicação de texturas tridimensionais realistas em malhas (meshes) no **Blender** usando Inteligência Artificial (**Hunyuan3D-Paint**).

O ecossistema é dividido em duas partes principais:
1. **FastAPI Backend (Servidor Local)**: Um microsserviço Python que gerencia os modelos de IA, gera as imagens guias e executa a texturização. Ele possui um **Modo Mock** que gera texturas procedimentais em milissegundos para facilitar testes rápidos offline sem necessidade de GPU CUDA dedicada.
2. **Blender Add-on (Plugin)**: Um painel integrado à barra lateral (N-Panel) do Blender 3D que permite configurar parâmetros da IA, exportar o modelo selecionado, solicitar a texturização e reintegrar o resultado de volta ao cenário de forma automatizada.

---

## 🛠️ Arquitetura do Sistema

```
[ Blender 3D ] <-- (HTTP / JSON + GLB) --> [ Servidor FastAPI ]
      │                                             │
      ├── Opção A: Importação GLB total             ├── Modo Real: Hunyuan3D-Paint (GPU)
      └── Opção B: Aplicação direta na UV           └── Modo Mock: Texturas Procedimentais (CPU)
```

---

## 🚀 Como Executar o Backend (Servidor Local)

O backend possui o script `run_backend.sh` para configurar e iniciar o ambiente de desenvolvimento de forma simplificada no Linux.

### Passo 1: Executar o Servidor FastAPI
Na raiz do workspace (`/home/yurix/Documentos/max-texturizer`), execute o script de inicialização:
```bash
./run_backend.sh
```
Isso irá:
1. Criar um ambiente virtual Python (`venv`) na pasta `backend/`.
2. Instalar as dependências descritas em `backend/requirements.txt`.
3. Iniciar o servidor local na porta `8009` (recarregável em tempo real).

Acesse a documentação interativa da API no navegador para testar os endpoints isoladamente:
👉 [http://127.0.0.1:8009/docs](http://127.0.0.1:8009/docs)

### 💡 Modo Mock vs Modo Real (Hunyuan3D-Paint)
- **Modo Mock (Padrão/Offline)**: Se o servidor não detectar uma GPU NVIDIA compatível com CUDA ou a biblioteca `hy3dgen` instalada, ele iniciará automaticamente no **Modo Mock**. Neste modo, o servidor gera mapas de textura (Albedo, Roughness, Normal) procedimentais com base nas palavras-chave do seu prompt (ex: madeira, metal, ouro) de forma instantânea.
- **Modo Real (Com GPU)**: Para rodar com IA real, garanta que seu ambiente virtual (`venv`) possua o PyTorch configurado com suporte a CUDA e a biblioteca `hy3dgen` instalada/compilada. O servidor baixará os pesos do modelo `tencent/Hunyuan3D-2` automaticamente do Hugging Face.

---

## 🔌 Instalação do Add-on no Blender

1. Compacte a pasta `blender_addon` em um arquivo ZIP. Você pode fazer isso via terminal na raiz do workspace:
   ```bash
   zip -r max_texturizer.zip blender_addon
   ```
2. Abra o **Blender** (versão 3.3 ou superior).
3. Vá em **Edit** > **Preferences** > **Add-ons**.
4. Clique em **Install...** no canto superior direito e selecione o arquivo `max_texturizer.zip` criado.
5. Marque a caixa de seleção ao lado de **3D View: Max Texturizer IA** para ativá-lo.
6. (Opcional) Expanda as configurações do Add-on para ajustar a URL do servidor backend se necessário (Padrão: `http://127.0.0.1:8009`).

---

## 🎮 Como Usar no Blender

Abra o painel lateral do Blender pressionando a tecla `N` na Viewport 3D e selecionando a aba **Max Texturizer**.

1. **Verificar Conexão**: Clique em **Verificar Conexão** para checar se o add-on está se comunicando com o servidor FastAPI. O painel exibirá o modo ativo (Mock ou Real) e o dispositivo de processamento.
2. **Configurar o Prompt**: No campo **Prompt**, digite a textura desejada (Ex: `madeira rústica de carvalho, veios escuros`). Digite termos para evitar no campo **Negativo**.
3. **Visualizar Imagem Guia**: Clique no botão **Visualizar Imagem de Referência**. O servidor gerará uma imagem preliminar de referência. Abra o **Editor de Imagens** do Blender e escolha `MaxTexturizer_Preview` para inspecionar o visual da imagem que guiará a pintura.
4. **Escolher o Método de Aplicação**:
   - **Mapear UVs Existentes (Recomendado para malhas autorais)**: O add-on exporta seu modelo, gera as texturas e constrói um material PBR (Albedo, Roughness e Normal Map) completo no Blender aplicando nas coordenadas UV existentes do seu objeto.
   - **Substituir por Malha .glb**: O add-on substitui seu objeto original por uma nova malha importada com coordenadas de textura totalmente geradas e otimizadas pela IA.
5. **Gerar**: Clique no botão **Gerar Textura**. O processo é disparado e, em instantes, o seu modelo 3D será atualizado na Viewport!
