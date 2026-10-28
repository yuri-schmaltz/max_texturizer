"""Launcher lifecycle tests; Blender and model weights are not needed."""
import importlib.util
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    'backend_service', Path(__file__).resolve().parents[1] / 'blender_addon/backend_service.py'
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
REAL_HEALTH = {'status': 'running', 'is_mock': False, 'mode': 'AI Model Mode (Hunyuan3D-Paint)'}


class BackendServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = module.BackendService()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / 'run_backend.sh').touch()
        self.service.log_path = self.project / 'backend.log'
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            self.port = listener.getsockname()[1]
        self.url = f'http://127.0.0.1:{self.port}'

    def test_flatpak_uses_host_python_and_cuda(self):
        with patch.dict(os.environ, {'FLATPAK_ID': 'org.blender.Blender'}):
            command = module.launch_command(self.project, '127.0.0.1', self.port, False)
        self.assertEqual(command[:2], ['flatpak-spawn', '--host'])
        self.assertIn('LD_LIBRARY_PATH', command)
        self.assertIn('PORT=' + str(self.port), command)
        self.assertEqual(command[-3:], ['bash', str(self.project / 'run_backend.sh'), '--real'])

    def test_existing_real_backend_is_reused(self):
        with patch.object(module, 'probe_health', return_value=REAL_HEALTH), patch.object(module.subprocess, 'Popen') as spawn:
            self.service._run(self.url, '', False)
        spawn.assert_not_called()
        self.assertEqual(self.service.snapshot()['status'], 'ready')

    def test_mock_server_does_not_masquerade_as_real(self):
        with patch.object(module, 'probe_health', return_value=dict(REAL_HEALTH, is_mock=True)):
            self.service._run(self.url, '', False)
        self.assertEqual(self.service.snapshot()['status'], 'error')
        self.assertIn('Mock', self.service.snapshot()['message'])

    def test_failed_child_is_reported_and_blender_environment_is_removed(self):
        child = Mock(returncode=7)
        child.poll.return_value = 7
        with patch.object(module, 'probe_health', side_effect=OSError('offline')), \
                patch.object(module.subprocess, 'Popen', return_value=child) as spawn, \
                patch.dict(os.environ, {'PYTHONHOME':'blender', 'PYTHONPATH':'blender', 'FORCE_MOCK':'true', 'RELOAD':'true'}):
            self.service._run(self.url, str(self.project), False)
        self.assertEqual(self.service.snapshot()['status'], 'error')
        self.assertIn('código 7', self.service.snapshot()['message'])
        args, options = spawn.call_args
        self.assertEqual(args[0], ['bash', str(self.project / 'run_backend.sh'), '--real'])
        self.assertEqual(options['env']['PORT'], str(self.port))
        self.assertEqual(options['env']['FORCE_MOCK'], 'false')
        self.assertEqual(options['env']['RELOAD'], 'false')
        self.assertNotIn('PYTHONHOME', options['env'])
        self.assertNotIn('PYTHONPATH', options['env'])
        self.assertTrue(options['start_new_session'])

    def test_occupied_port_never_spawns_a_second_process(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', self.port))
            listener.listen()
            with patch.object(module, 'probe_health', side_effect=OSError('offline')), patch.object(module.subprocess, 'Popen') as spawn:
                self.service._run(self.url, str(self.project), False)
        spawn.assert_not_called()
        self.assertIn('ocupada', self.service.snapshot()['message'])

    def test_check_without_auto_start_never_launches(self):
        with patch.object(module, 'probe_health', side_effect=OSError('offline')), patch.object(module.subprocess, 'Popen') as spawn:
            self.service.check(self.url)
            self.service._thread.join(2)
        spawn.assert_not_called()
        self.assertEqual(self.service.snapshot()['status'], 'error')

    def test_repeated_clicks_share_one_background_worker(self):
        entered, release = threading.Event(), threading.Event()
        def probe(url):
            entered.set()
            release.wait(2)
            return REAL_HEALTH
        with patch.object(module, 'probe_health', side_effect=probe) as health:
            self.service.start(self.url)
            self.assertTrue(entered.wait(1))
            original = self.service._thread
            self.service.start(self.url)
            self.assertIs(self.service._thread, original)
            release.set()
            original.join(2)
        self.assertEqual(health.call_count, 1)
        self.assertEqual(self.service.snapshot()['status'], 'ready')

    def test_remote_address_cannot_launch_local_process(self):
        with patch.object(module, 'probe_health', side_effect=OSError('offline')), patch.object(module.subprocess, 'Popen') as spawn:
            self.service._run('http://192.0.2.1:8009', str(self.project), False)
        spawn.assert_not_called()
        self.assertIn('endereço local', self.service.snapshot()['message'])


if __name__ == '__main__':
    unittest.main()
