#!/bin/bash

# Max Texturizer Backend Service Runner
# Configura o venv, instala dependências e inicia o FastAPI

set -e

# Navega para o diretório do script
cd "$(dirname "$0")"

# Se executado da raiz do projeto, entra na pasta backend
if [ -d "backend" ]; then
    cd backend
fi

echo "=========================================================="
echo "          INICIALIZANDO MAX TEXTURIZER BACKEND            "
echo "=========================================================="

# 1. Criar ambiente virtual
if [ ! -d "venv" ]; then
    echo "[+] Criando ambiente virtual Python (venv)..."
    python3 -m venv venv
fi

# 2. Ativar ambiente
echo "[+] Ativando ambiente virtual..."
source venv/bin/activate

# 3. Instalar pacotes
echo "[+] Atualizando pip..."
pip install --upgrade pip

echo "[+] Instalando dependências em requirements.txt..."
# Nota: Para o modo mock, xatlas, torch e diffusers são instalados normalmente.
# Se o usuário desejar compilar os módulos CUDA reais do Hunyuan3D-Paint,
# ele precisará seguir o README.md e ter o CUDA Toolkit instalado.
pip install -r requirements.txt

# 4. Iniciar uvicorn
echo "=========================================================="
echo "[+] Servidor pronto para execução!"
echo "[*] Rodando em http://127.0.0.1:8009"
echo "[*] Acesse http://127.0.0.1:8009/docs para Swagger UI"
echo "=========================================================="

python3 main.py
