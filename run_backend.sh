#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
project_dir="$PWD"
mode="${TEXTURIZER_MODE:-auto}"
case "${1:-}" in
    --real) mode=real ;;
    --mock) mode=mock ;;
    '') ;;
    *) echo "Uso: $0 [--real|--mock]" >&2; exit 2 ;;
esac
if [[ "${FORCE_MOCK:-false}" == true ]]; then
    mode=mock
fi
if [[ "$mode" == auto ]]; then
    if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
        mode=real
    else
        mode=mock
    fi
fi
case "$mode" in real|mock) ;; *) echo 'TEXTURIZER_MODE deve ser auto, real ou mock.' >&2; exit 2 ;; esac

echo '=========================================================='
echo "          MAX TEXTURIZER BACKEND — modo $mode"
echo '=========================================================='
if python3 backend/check_port.py "$mode"; then
    : # The address is free.
else
    port_status=$?
    if [[ "$port_status" == 10 ]]; then
        exit 0
    fi
    exit "$port_status"
fi
if [[ ! -x backend/venv/bin/python ]]; then
    python3 -m venv backend/venv
fi
python_bin="$project_dir/backend/venv/bin/python"
if [[ "$mode" == real ]]; then
    "$project_dir/install_hunyuan.sh"
    export REQUIRE_REAL=true FORCE_MOCK=false
else
    "$python_bin" -m pip install -r backend/requirements.txt
    export FORCE_MOCK=true REQUIRE_REAL=false
fi
echo "[*] Iniciando em http://${HOST:-127.0.0.1}:${PORT:-8009}"
echo '[*] No modo real, a primeira inicialização baixa os pesos antes de aceitar conexões.'
cd backend
exec "$python_bin" main.py
