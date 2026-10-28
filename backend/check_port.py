"""Check the listening address before installing dependencies or loading weights."""
import errno
import json
import os
import socket
import sys
from urllib.request import ProxyHandler, Request, build_opener


def check_port(mode):
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8009"))
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as listener:
            listener.bind((host, port))
        return 0
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            print(f"Não foi possível usar {host}:{port}: {error}", file=sys.stderr)
            return 1

    probe_host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    if ":" in probe_host:
        probe_host = f"[{probe_host}]"
    url = f"http://{probe_host}:{port}"
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(Request(f"{url}/health"), timeout=3) as response:
            health = json.load(response)
        expected_mode = "Mock Mode (Procedural)" if mode == "mock" else "AI Model Mode (Hunyuan3D-Paint)"
        if (health.get("status") == "running"
                and health.get("mode") == expected_mode
                and health.get("is_mock") is (mode == "mock")):
            print(f"[+] Max Texturizer já está rodando em {url} — {expected_mode}.")
            print("[*] Use Verificar Conexão no Blender. Nenhum segundo servidor foi iniciado.")
            return 10
    except (OSError, ValueError, AttributeError):
        pass
    print(f"A porta {port} em {host} já está ocupada por outro serviço ou modo. "
          "Encerre esse processo ou escolha outra porta com PORT=8010.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(check_port(sys.argv[1]))
