import unittest
from unittest import mock

import keystore


class KeystoreWithoutBackendTests(unittest.TestCase):
    """The OS credential store is never touched: _OK is forced off."""

    def test_no_keyring_means_no_key_and_failed_writes(self):
        with mock.patch.object(keystore, "_OK", False):
            self.assertFalse(keystore.available())
            self.assertIsNone(keystore.get_key())
            self.assertFalse(keystore.set_key("sk-x"))
