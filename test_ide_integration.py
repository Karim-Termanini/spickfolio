import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from spick_folio import config
from spick_folio.ide_integration import (
    detect_available_ides,
    find_ide_executable,
    send_code_to_ide,
)


class IdeDetectionTests(unittest.TestCase):
    @patch('spick_folio.ide_integration.shutil.which', return_value='/usr/bin/code')
    def test_find_vscode(self, _which):
        self.assertEqual(find_ide_executable('vscode'), '/usr/bin/code')

    @patch('spick_folio.ide_integration.shutil.which', return_value=None)
    def test_find_rstudio_missing(self, _which):
        with patch('spick_folio.ide_integration._is_executable', return_value=False):
            self.assertIsNone(find_ide_executable('rstudio'))

    @patch('spick_folio.ide_integration.find_ide_executable', side_effect=lambda ide: f'/bin/{ide}')
    def test_detect_available_ides(self, _find):
        ides = detect_available_ides()
        self.assertTrue(ides['vscode'])
        self.assertTrue(ides['cursor'])
        self.assertTrue(ides['rstudio'])


class SendCodeToIdeTests(unittest.TestCase):
    def test_rejects_invalid_ide(self):
        ok, err = send_code_to_ide('vim', 'x <- 1', 'r')
        self.assertFalse(ok)
        self.assertEqual(err, 'ide_invalid')

    def test_rejects_missing_code(self):
        ok, err = send_code_to_ide('vscode', '   ', 'r')
        self.assertFalse(ok)
        self.assertEqual(err, 'ide_code_missing')

    def test_rejects_invalid_language(self):
        ok, err = send_code_to_ide('vscode', 'print(1)', 'julia')
        self.assertFalse(ok)
        self.assertEqual(err, 'ide_language_invalid')

    @patch('spick_folio.ide_integration.find_ide_executable', return_value=None)
    def test_ide_not_found(self, _find):
        ok, err = send_code_to_ide('vscode', 'print(1)', 'python')
        self.assertFalse(ok)
        self.assertEqual(err, 'ide_not_found')

    @patch('spick_folio.ide_integration._open_in_editor', return_value=True)
    @patch('spick_folio.ide_integration.find_ide_executable', return_value='/usr/bin/code')
    def test_send_to_vscode_writes_snippet(self, _find, _open):
        root = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            with patch.object(config, 'CACHE_DIR', tmp):
                ok, mode = send_code_to_ide('vscode', 'print(1)', 'python')
            self.assertTrue(ok)
            self.assertEqual(mode, 'editor')
            snippet = os.path.join(tmp, 'ide', 'spickfolio_load.py')
            self.assertTrue(os.path.isfile(snippet))
            with open(snippet, encoding='utf-8') as handle:
                self.assertIn('print(1)', handle.read())

    @patch('spick_folio.ide_integration.subprocess.Popen')
    @patch('spick_folio.ide_integration.find_ide_executable', return_value='/usr/bin/rstudio')
    def test_send_to_rstudio_opens_file(self, _find, mock_popen):
        mock_popen.return_value = MagicMock()
        root = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            with patch.object(config, 'CACHE_DIR', tmp):
                ok, mode = send_code_to_ide('rstudio', 'df <- read.csv("a.csv")', 'r')
            self.assertTrue(ok)
            self.assertEqual(mode, 'editor')
            mock_popen.assert_called_once()
            self.assertIn('/usr/bin/rstudio', mock_popen.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
