import os
import unittest
from unittest.mock import patch

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
        self.assertIn('fehlt', err)

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
    @patch('stats_sheets.desktop_actions.subprocess.run')
    @patch('stats_sheets.desktop_actions.validate_open_path')
    def test_open_path_in_file_manager_uses_directory_for_files(self, mock_validate, mock_run, _which):
        mock_validate.return_value = ('/home/user/Downloads/data.csv', None)
        mock_run.return_value.returncode = 0
        ok, err = open_path_in_file_manager('/home/user/Downloads/data.csv')
        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_run.assert_called_once_with(['/usr/bin/xdg-open', '/home/user/Downloads'], capture_output=True, text=True, timeout=10)

    @patch('stats_sheets.desktop_actions.shutil.which', return_value='/usr/bin/xdg-open')
    @patch('stats_sheets.desktop_actions.subprocess.run')
    @patch('stats_sheets.desktop_actions.validate_open_path')
    def test_open_path_on_desktop_opens_file(self, mock_validate, mock_run, _which):
        mock_validate.return_value = ('/home/user/Downloads/data.csv', None)
        mock_run.return_value.returncode = 0
        with patch('stats_sheets.desktop_actions.os.path.isfile', return_value=True):
            ok, err = open_path_on_desktop('/home/user/Downloads/data.csv', action='file')
        self.assertTrue(ok)
        mock_run.assert_called_once_with(['/usr/bin/xdg-open', '/home/user/Downloads/data.csv'], capture_output=True, text=True, timeout=10)

    @patch('stats_sheets.desktop_actions.shutil.which', return_value='/usr/bin/notify-send')
    @patch('stats_sheets.desktop_actions.subprocess.run')
    def test_send_desktop_notification(self, mock_run, _which):
        mock_run.return_value.returncode = 0
        ok, err = send_desktop_notification('Title', 'Body text')
        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_run.assert_called_once_with(['/usr/bin/notify-send', 'Title', 'Body text'], capture_output=True, text=True, timeout=5)


if __name__ == '__main__':
    unittest.main()
