#!/usr/bin/env bash
# Install the real paint engine into this project's backend environment.
set -euo pipefail
cd "$(dirname "$0")"
python_bin="$PWD/backend/venv/bin/python"
source_dir="$PWD/backend/vendor/Hunyuan3D-2"
revision=f8db63096c8282cb27354314d896feba5ba6ff8a
install_key="$revision:$(sha256sum backend/requirements.txt backend/requirements-ai.txt | sha256sum | cut -d' ' -f1)"

if [[ ! -x "$python_bin" ]]; then
    echo 'Ambiente ausente. Execute ./run_backend.sh --real.' >&2
    exit 1
fi
for tool in git nvcc g++; do
    if ! command -v "$tool" >/dev/null; then
        echo "Falta $tool. Instale Git, CUDA Toolkit (nvcc) e compilador C++ antes do modo real." >&2
        exit 1
    fi
done
# CUDA 12.x is required by the selected PyTorch wheels.
if ! nvcc --version | grep -q 'release 12\.'; then
    echo 'Esta instalação usa PyTorch cu124 e requer CUDA Toolkit 12.x no PATH.' >&2
    exit 1
fi
export MAX_JOBS="${MAX_JOBS:-2}"
# CUDA 12.0 does not support GCC 13, which is the default on Ubuntu 24.04.
if command -v g++-12 >/dev/null && [[ -z "${CXX:-}" ]]; then
    export CXX=g++-12
    export CC=gcc-12
fi
if [[ -f "$source_dir/.texturizer-installed" ]] &&
   [[ "$(cat "$source_dir/.texturizer-installed")" == "$install_key" ]] &&
   "$python_bin" -c 'import torch, torchvision, custom_rasterizer, custom_rasterizer_kernel, mesh_processor; from hy3dgen.texgen import Hunyuan3DPaintPipeline; assert torch.cuda.is_available(); assert torch.__version__.startswith("2.6.0")' >/dev/null; then
    echo '[+] Hunyuan3D e extensões já instalados.'
    exit 0
fi
"$python_bin" -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
"$python_bin" -c 'import torch; assert torch.cuda.is_available(), "CUDA indisponível: verifique o driver NVIDIA"'
"$python_bin" -m pip install -r backend/requirements.txt -r backend/requirements-ai.txt
if [[ ! -d "$source_dir" ]]; then
    mkdir -p "$(dirname "$source_dir")"
    git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git "$source_dir"
fi
# Never overwrite changes in an existing source checkout.
git -C "$source_dir" checkout "$revision"
"$python_bin" -m pip install --no-deps --no-build-isolation -e "$source_dir"
for extension in custom_rasterizer differentiable_renderer; do
    "$python_bin" -m pip install --no-deps --no-build-isolation "$source_dir/hy3dgen/texgen/$extension"
done
"$python_bin" -c 'import torch, custom_rasterizer, custom_rasterizer_kernel, mesh_processor; from hy3dgen.texgen import Hunyuan3DPaintPipeline; print("[+] hy3dgen e extensões importados com sucesso.")'
printf '%s\n' "$install_key" > "$source_dir/.texturizer-installed"
