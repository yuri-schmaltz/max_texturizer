"""Discover local LLMs without blocking Blender or touching bpy in a thread."""
import json
import threading
from urllib.parse import urlsplit, urlunsplit
from urllib.request import ProxyHandler, build_opener


def model_endpoints(url):
    parsed = urlsplit(url.strip().rstrip('/'))
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError('Informe uma URL HTTP válida para o Ollama/LM Studio.')
    path = parsed.path.rstrip('/')
    if path.endswith('/v1'):
        return [(urlunsplit(parsed._replace(path=path + '/models')), 'openai')]
    return [(urlunsplit(parsed._replace(path=path + '/api/tags')), 'ollama'),
            (urlunsplit(parsed._replace(path=path + '/v1/models')), 'openai')]


def fetch_models(url):
    errors = []
    opener = build_opener(ProxyHandler({}))
    for endpoint, provider in model_endpoints(url):
        try:
            with opener.open(endpoint, timeout=4) as response:
                data = json.load(response)
            key = 'models' if provider == 'ollama' else 'data'
            if not isinstance(data, dict) or not isinstance(data.get(key), list):
                raise ValueError('resposta sem lista de modelos')
            names = set()
            for item in data[key]:
                if not isinstance(item, dict):
                    continue
                name = (item.get('name') or item.get('model')) if provider == 'ollama' else item.get('id')
                if isinstance(name, str) and name.strip():
                    names.add(name.strip())
            return tuple(sorted(names, key=str.casefold)), provider
        except (OSError, ValueError) as error:
            errors.append(str(error))
    raise RuntimeError('Não foi possível listar os modelos. Verifique a URL e se o servidor LLM está ativo. ' + '; '.join(errors))


class ModelCatalog:
    def __init__(self):
        self._lock = threading.Lock()
        self._generation = 0
        self._thread = None
        self._state = {'url': '', 'status': 'idle', 'models': (), 'message': 'Modelos ainda não consultados'}

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def refresh(self, url):
        url = url.strip().rstrip('/')
        with self._lock:
            if self._state['url'] == url and self._state['status'] == 'loading':
                return
            models = self._state['models'] if self._state['url'] == url else ()
            self._generation += 1
            generation = self._generation
            self._state = {'url': url, 'status': 'loading', 'models': models, 'message': 'Buscando modelos…'}
            self._thread = threading.Thread(target=self._fetch, args=(url, generation), daemon=True)
            self._thread.start()

    def _fetch(self, url, generation):
        try:
            models, provider = fetch_models(url)
            message = f'{len(models)} modelo(s) disponível(is)' if models else 'Nenhum modelo disponível neste servidor'
            result = {'url': url, 'status': 'ready', 'models': models, 'message': message, 'provider': provider}
        except Exception as error:
            result = {'url': url, 'status': 'error', 'message': str(error)}
        with self._lock:
            if generation == self._generation:
                self._state.update(result)


catalog = ModelCatalog()
