import importlib.util
import io
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('llm_models', Path(__file__).resolve().parents[1] / 'blender_addon/llm_models.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModelDiscoveryTests(unittest.TestCase):
    def test_ollama_names_are_deduplicated_sorted_and_validated(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"models":[{"name":"z:latest"},{"model":"a:7b"},{"name":"a:7b"},null,{"name":4}]}')
        with patch.object(module, 'build_opener', return_value=opener):
            names, provider = module.fetch_models('http://localhost:11434/')
        self.assertEqual(names, ('a:7b', 'z:latest'))
        self.assertEqual(provider, 'ollama')
        self.assertEqual(opener.open.call_args.args[0], 'http://localhost:11434/api/tags')

    def test_openai_fallback(self):
        opener = Mock()
        opener.open.side_effect = [OSError('404'), io.BytesIO(b'{"data":[{"id":"qwen"}]}')]
        with patch.object(module, 'build_opener', return_value=opener):
            self.assertEqual(module.fetch_models('http://localhost:1234'), (('qwen',), 'openai'))
        self.assertEqual(opener.open.call_args.args[0], 'http://localhost:1234/v1/models')

    def test_v1_suffix_not_duplicated_and_proxy_path_preserved(self):
        self.assertEqual(module.model_endpoints('http://localhost:1234/proxy/v1/'), [('http://localhost:1234/proxy/v1/models', 'openai')])

    def test_empty_is_a_success_not_a_connection_error(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"models":[]}')
        with patch.object(module, 'build_opener', return_value=opener):
            self.assertEqual(module.fetch_models('http://localhost:11434'), ((), 'ollama'))

    def test_failed_refresh_keeps_previous_models_only_for_same_server(self):
        catalog = module.ModelCatalog()
        with patch.object(module, 'fetch_models', return_value=(('model-a',), 'ollama')):
            catalog.refresh('http://localhost:11434')
            catalog._thread.join(2)
        with patch.object(module, 'fetch_models', side_effect=OSError('offline')):
            catalog.refresh('http://localhost:11434')
            catalog._thread.join(2)
            self.assertEqual(catalog.snapshot()['models'], ('model-a',))
            self.assertEqual(catalog.snapshot()['status'], 'error')
            catalog.refresh('http://localhost:1234')
            catalog._thread.join(2)
        self.assertEqual(catalog.snapshot()['models'], ())

    def test_slow_old_url_cannot_replace_new_server_models(self):
        catalog = module.ModelCatalog()
        entered, release = threading.Event(), threading.Event()
        def fetch(url):
            if url.endswith('11434'):
                entered.set()
                release.wait(2)
                return ('old',), 'ollama'
            return ('new',), 'openai'
        with patch.object(module, 'fetch_models', side_effect=fetch):
            catalog.refresh('http://localhost:11434')
            old = catalog._thread
            self.assertTrue(entered.wait(1))
            catalog.refresh('http://localhost:1234')
            catalog._thread.join(2)
            release.set()
            old.join(2)
        self.assertEqual(catalog.snapshot()['models'], ('new',))
        self.assertEqual(catalog.snapshot()['url'], 'http://localhost:1234')

    def test_rejects_non_http_addresses(self):
        with self.assertRaises(ValueError):
            module.model_endpoints('file:///etc/passwd')


if __name__ == '__main__':
    unittest.main()
