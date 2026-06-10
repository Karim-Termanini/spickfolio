import unittest

from spick_folio import config
from spick_folio.rate_limit import is_rate_limited, reset_rate_limit_state


class RateLimitResetTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_state()

    def tearDown(self):
        reset_rate_limit_state()

    def test_reset_clears_rate_limit_window(self):
        ip = '10.0.0.1'
        for _ in range(config.RATE_LIMIT_MAX):
            self.assertFalse(is_rate_limited(ip))
        self.assertTrue(is_rate_limited(ip))
        reset_rate_limit_state()
        self.assertFalse(is_rate_limited(ip))


if __name__ == '__main__':
    unittest.main()
