import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from stats_sheets.desktop_actions import (
    open_path_in_file_manager,
    open_path_on_desktop,
    send_desktop_notification,
    validate_open_path,
)


class ValidateOpenPathTests(unittest.TestCase):
    def test_rejects_missing_path(self):
        resolved, err = validate_open_path('')
        self.assertIsNone(resolved)
        self.assertEqual(err, 'open_path_missing')

    def test_rejects_denied_prefix(self):
        resolved, err = validate_open_path('/etc/passwd')
        self.assertIsNone(resolved)

    def test_accepts_existing_file_in_downloads(self):
        downloads = os.path.expanduser('~/Downloads')
        if not os.path.isdir(downloads):
            self.skipTest('~/Downloads not available')
        resolved, err = validate_open_path(downloads)
        self.assertIsNone(err)
        self.assertTrue(os.path.isdir(resolved))


class DesktopActionTests(unittest.TestCase):
    @patch('stats_sheets.desktop_actions.shutil.which', return_value='/usr/bin/xdg-open')
    @patch('stats_sheets.desktop_actions.subprocess.Popen')
    @patch('stats_sheets.desktop_actions.validate_open_path')
    def test_open_path_in_file_manager_uses_directory_for_files(self, mock_validate, mock_popen, _which):
        mock_validate.return_value = ('/home/user/Downloads/data.csv', None)
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc
        ok, err = open_path_in_file_manager('/home/user/Downloads/data.csv')
        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_popen.assert_called_once()
        self.assertEqual(mock_popen.call_args.args[0], ['/usr/bin/xdg-open', '/home/user/Downloads'])

    @patch('stats_sheets.desktop_actions.shutil.which', return_value='/usr/bin/xdg-open')
    @patch('stats_sheets.desktop_actions.subprocess.Popen')
    @patch('stats_sheets.desktop_actions.validate_open_path')
    def test_open_path_succeeds_when_xdg_open_stays_running(self, mock_validate, mock_popen, _which):
        mock_validate.return_value = ('/home/user/Documents', None)
        mock_proc = MagicMock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd='xdg-open', timeout=2)
        mock_popen.return_value = mock_proc
        ok, err = open_path_in_file_manager('/home/user/Documents')
        self.assertTrue(ok)
        self.assertIsNone(err)

    @patch('stats_sheets.desktop_actions.shutil.which', return_value='/usr/bin/xdg-open')
    @patch('stats_sheets.desktop_actions.subprocess.Popen')
    @patch('stats_sheets.desktop_actions.validate_open_path')
    def test_open_path_on_desktop_opens_file(self, mock_validate, mock_popen, _which):
        mock_validate.return_value = ('/home/user/Downloads/data.csv', None)
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc
        with patch('stats_sheets.desktop_actions.os.path.isfile', return_value=True):
            ok, err = open_path_on_desktop('/home/user/Downloads/data.csv', action='file')
        self.assertTrue(ok)
        mock_popen.assert_called_once_with(
            ['/usr/bin/xdg-open', '/home/user/Downloads/data.csv'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    @patch('stats_sheets.desktop_actions.shutil.which', return_value='/usr/bin/notify-send')
    @patch('stats_sheets.desktop_actions.subprocess.run')
    def test_send_desktop_notification(self, mock_run, _which):
        mock_run.return_value.returncode = 0
        ok, err = send_desktop_notification('Title', 'Body text')
        self.assertTrue(ok)
        self.assertIsNone(err)


if __name__ == '__main__':
    unittest.main()
