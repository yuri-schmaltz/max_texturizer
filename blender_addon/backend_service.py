"""Launch and monitor the local backend without accessing Blender from threads."""
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


def find_backend_directory(configured=""):
    if configured:
        candidates = [Path(configured).expanduser()]
    else:
        candidates = []
        if os.getenv("MAX_TEXTURIZER_ROOT"):
            candidates.append(Path(os.environ["MAX_TEXTURIZER_ROOT"]).expanduser())
        # The installation ZIP records the checkout used to build it.
        location = Path(__file__).with_name("backend_location.json")
        if location.is_file():
            try:
                candidates.append(Path(json.loads(location.read_text())["directory"]).expanduser())
            except (OSError, ValueError, KeyError, TypeError):
                pass
        candidates.append(Path(__file__).resolve().parent.parent)
    for candidate in candidates:
        if (candidate / "run_backend.sh").is_file():
            return candidate.resolve()
    raise RuntimeError("Selecione a pasta do projeto nas preferências do add-on (a pasta que contém run_backend.sh).")


def local_address(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise RuntimeError("Para iniciar o backend, use um endereço local, como http://127.0.0.1:8009.")
    return parsed.hostname, parsed.port or 80


def probe_health(url):
    opener = build_opener(ProxyHandler({}))
    with opener.open(url.rstrip("/") + "/health", timeout=1) as response:
        data = json.load(response)
    if (not isinstance(data, dict) or data.get("status") != "running"
            or type(data.get("is_mock")) is not bool
            or data.get("mode") not in {"Mock Mode (Procedural)", "AI Model Mode (Hunyuan3D-Paint)"}):
        raise RuntimeError("O endereço respondeu, mas não corresponde ao Max Texturizer.")
    return data


def launch_command(project, host, port, force_mock):
    command = ["bash", str(project / "run_backend.sh"), "--mock" if force_mock else "--real"]
    if os.getenv("FLATPAK_ID") or Path("/.flatpak-info").exists():
        # Use the host Python/CUDA libraries, not Blender's Flatpak runtime.
        command = [
            "flatpak-spawn", "--host", "--directory=" + str(project),
            "/usr/bin/env", "-u", "PYTHONHOME", "-u", "PYTHONPATH", "-u", "VIRTUAL_ENV",
            "-u", "LD_LIBRARY_PATH", "PATH=/usr/local/bin:/usr/bin:/bin",
            "HOST=" + host, "PORT=" + str(port), "RELOAD=false",
            "FORCE_MOCK=" + ("true" if force_mock else "false"),
        ] + command
    return command


class BackendService:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._process = None
        self._url = ""
        self._state = {"status": "idle", "message": "Backend ainda não verificado", "health": None}
        self.log_path = Path.home() / ".cache" / "max-texturizer" / "backend.log"

    def snapshot(self):
        with self._lock:
            return dict(self._state, url=self._url)

    def _set(self, status, message, health=None):
        with self._lock:
            self._state = {"status": status, "message": message, "health": health}

    def check(self, url):
        self.start(url, force_mock=True, allow_launch=False)

    def start(self, url, directory="", force_mock=False, allow_launch=True):
        # Only this small state update runs on Blender's main thread.
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._url = url.rstrip("/")
            self._state = {"status": "checking", "message": "Verificando backend…", "health": None}
            self._thread = threading.Thread(
                target=self._run, args=(url, directory, force_mock, allow_launch), daemon=True,
                name="MaxTexturizerBackend",
            )
            self._thread.start()

    def _ready(self, health, force_mock):
        if health["is_mock"] and not force_mock:
            raise RuntimeError("O servidor existente está em Mock. Encerre-o para iniciar o modo real, ou habilite Forçar Modo Mock.")
        mode = "Mock" if health["is_mock"] else "Hunyuan3D / CUDA"
        self._set("ready", f"Conectado: {mode}", health)

    def _run(self, url, directory, force_mock, allow_launch=True):
        try:
            try:
                health = probe_health(url)
            except (OSError, ValueError):
                health = None
            if health is not None:
                self._ready(health, force_mock)
                return
            if not allow_launch:
                raise RuntimeError("Backend indisponível. Clique em Iniciar Backend ou habilite a inicialização automática nas preferências.")
            host, port = local_address(url)
            # Reattach to a child still loading after an earlier monitor timeout.
            if self._process is None or self._process.poll() is not None:
                with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM) as listener:
                    try:
                        listener.bind((host, port))
                    except OSError as error:
                        raise RuntimeError(f"A porta {port} está ocupada e o backend não respondeu. Aguarde o carregamento ou confira o serviço nessa porta.") from error
                project = find_backend_directory(directory)
                if os.name != "posix":
                    raise RuntimeError("O inicializador run_backend.sh requer Linux ou outro sistema com Bash.")
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                env = os.environ.copy()
                # Blender's embedded Python must not leak into the system venv.
                for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
                    env.pop(name, None)
                env.update(HOST=host, PORT=str(port), RELOAD="false", FORCE_MOCK="true" if force_mock else "false")
                with self.log_path.open("w", encoding="utf-8") as log:
                    self._process = subprocess.Popen(
                        launch_command(project, host, port, force_mock),
                        cwd=str(project), env=env, stdin=subprocess.DEVNULL,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                    )
            self._set("starting", "Preparando backend e carregando modelos…")
            deadline = time.monotonic() + 3600  # First install can download many GB.
            while time.monotonic() < deadline:
                try:
                    health = probe_health(url)
                except (OSError, ValueError):
                    health = None
                if health is not None:
                    self._ready(health, force_mock)
                    return
                if self._process.poll() is not None:
                    raise RuntimeError(f"O backend encerrou (código {self._process.returncode}). Consulte Abrir log do backend.")
                time.sleep(2)
            raise RuntimeError("O backend ainda não respondeu após uma hora. Confira o log; Verificar Conexão tenta novamente.")
        except Exception as error:
            self._set("error", str(error))


service = BackendService()
