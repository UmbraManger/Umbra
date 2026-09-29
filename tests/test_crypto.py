import json
import os
import unittest
from unittest import mock

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import crypto
from .helpers import IsolatedCase, known_bug

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4


def blob_file(img_id):
    return os.path.join(crypto.ENC_DIR, img_id + ".bin")


def read(path):
    with open(path, "rb") as f:
        return f.read()


class UnprotectedStorageTests(IsolatedCase):
    def test_store_and_load_round_trip_when_protection_is_off(self):
        img_id = crypto.store_image(PNG, "image/png")
        self.assertRegex(img_id, crypto.IMG_ID_RE.pattern)
        self.assertEqual(crypto.load_image(img_id), (PNG, "image/png"))
        self.assertEqual(read(blob_file(img_id)), PNG)   # plaintext on disk

    def test_image_id_validation_blocks_path_traversal(self):
        self.assertIsNone(crypto.load_image("../../etc/passwd"))
        self.assertIsNone(crypto.load_image("i1234"))
        self.assertIsNone(crypto.load_image(""))
        sentinel = os.path.join(self.data, "sentinel.bin")
        with open(sentinel, "wb") as f:
            f.write(b"keep")
        crypto.remove_image("../sentinel")
        self.assertTrue(os.path.exists(sentinel))

    def test_remove_image_deletes_blob_and_metadata(self):
        img_id = crypto.store_image(PNG, "image/png")
        crypto.remove_image(img_id)
        self.assertIsNone(crypto.load_image(img_id))
        self.assertFalse(os.path.exists(blob_file(img_id)))


class ProtectedStorageTests(IsolatedCase):
    PW = "correct horse"

    def setUp(self):
        super().setUp()
        crypto.set_passphrase(self.PW)

    def test_setting_a_passphrase_turns_protection_on_and_unlocks(self):
        self.assertEqual(crypto.status(),
                         {"on": True, "pass_set": True, "unlocked": True})

    def test_protected_images_are_encrypted_on_disk_and_readable(self):
        img_id = crypto.store_image(PNG, "image/png")
        raw = read(blob_file(img_id))
        self.assertNotEqual(raw, PNG)
        self.assertNotIn(PNG[:32], raw)
        self.assertEqual(crypto.load_image(img_id), (PNG, "image/png"))

    def test_locked_vault_refuses_reads_and_writes(self):
        img_id = crypto.store_image(PNG, "image/png")
        crypto._state["key"] = None
        with self.assertRaises(crypto.Locked):
            crypto.load_image(img_id)
        with self.assertRaises(crypto.Locked):
            crypto.store_image(PNG, "image/png")     # never silently writes plaintext

    def test_unlock_rejects_wrong_passphrase_and_accepts_right_one(self):
        img_id = crypto.store_image(PNG, "image/png")
        crypto._state["key"] = None
        self.assertFalse(crypto.unlock("nope"))
        self.assertIsNone(crypto._state["key"])
        self.assertTrue(crypto.unlock(self.PW))
        self.assertEqual(crypto.load_image(img_id)[0], PNG)

    def test_meta_stores_a_verifier_not_a_fast_hash(self):
        meta = crypto._meta()
        self.assertIn("verifier", meta)
        self.assertNotIn("hash", meta)
        with open(crypto.META, encoding="utf-8") as f:
            self.assertNotIn(crypto._legacy_sha(self.PW), f.read())

    def test_changing_passphrase_rekeys_existing_blobs(self):
        ids = [crypto.store_image(PNG + bytes([i]), "image/png") for i in range(3)]
        crypto.set_passphrase("new pass", self.PW)
        crypto._state["key"] = None
        self.assertFalse(crypto.unlock(self.PW))
        self.assertTrue(crypto.unlock("new pass"))
        for i, img_id in enumerate(ids):
            self.assertEqual(crypto.load_image(img_id)[0], PNG + bytes([i]))

    def test_wrong_current_passphrase_changes_nothing(self):
        img_id = crypto.store_image(PNG, "image/png")
        before_blob, before_meta = read(blob_file(img_id)), read(crypto.META)
        with self.assertRaises(ValueError):
            crypto.set_passphrase("new pass", "wrong")
        self.assertEqual(read(blob_file(img_id)), before_blob)
        self.assertEqual(read(crypto.META), before_meta)

    def test_empty_passphrase_is_rejected(self):
        with self.assertRaises(ValueError):
            crypto.set_passphrase("")

    def test_encrypt_plaintext_requires_unlock_and_upgrades_plain_blobs(self):
        crypto.set_enabled(False)
        plain_id = crypto.store_image(PNG, "image/png")      # stored as plaintext
        self.assertEqual(read(blob_file(plain_id)), PNG)
        crypto.set_enabled(True)
        crypto._state["key"] = None
        with self.assertRaises(crypto.Locked):
            crypto.encrypt_plaintext()
        crypto.unlock(self.PW)
        self.assertEqual(crypto.encrypt_plaintext(), 1)
        self.assertNotEqual(read(blob_file(plain_id)), PNG)
        self.assertEqual(crypto.load_image(plain_id)[0], PNG)


class FirstPassphraseTests(IsolatedCase):
    def test_plain_blobs_are_folded_in_when_first_passphrase_is_set(self):
        plain_id = crypto.store_image(PNG, "image/png")
        crypto.set_passphrase("pw12")
        self.assertNotEqual(read(blob_file(plain_id)), PNG)
        self.assertEqual(crypto.load_image(plain_id), (PNG, "image/png"))


class LegacyMetaTests(IsolatedCase):
    def test_v1_meta_is_upgraded_and_existing_blobs_stay_readable(self):
        pw, salt = "oldpass", os.urandom(16)
        key = crypto._derive(pw, salt, crypto.KDF_PBKDF2_LEGACY)
        os.makedirs(crypto.ENC_DIR, exist_ok=True)
        iv = os.urandom(12)
        img_id = "iab12cd34"
        with open(blob_file(img_id), "wb") as f:
            f.write(iv + AESGCM(key).encrypt(iv, b"legacy-bytes", None))
        with open(os.path.join(crypto.ENC_DIR, img_id + ".json"), "w") as f:
            json.dump({"mime": "image/png", "enc": True}, f)
        crypto._save_meta({"on": True, "pass_set": True, "salt": salt.hex(),
                           "hash": crypto._legacy_sha(pw)})

        self.assertFalse(crypto.unlock("bad"))
        self.assertTrue(crypto.unlock(pw))
        meta = crypto._meta()
        self.assertIn("verifier", meta)
        self.assertNotIn("hash", meta)
        self.assertEqual(crypto.load_image(img_id)[0], b"legacy-bytes")
        crypto._state["key"] = None
        self.assertTrue(crypto.unlock(pw))          # works again via the v2 verifier


class RealKdfTests(IsolatedCase):
    fast_kdf = False

    def test_meta_records_the_kdf_actually_used(self):
        crypto.set_passphrase("pw12")
        kdf = crypto._meta()["kdf"]
        expected = "argon2id" if crypto._argon2_available() else "pbkdf2"
        self.assertEqual(kdf["type"], expected)
        crypto._state["key"] = None
        self.assertTrue(crypto.unlock("pw12"))


class KnownBugTests(IsolatedCase):
    @known_bug
    def test_failed_rekey_rolls_back_automatically(self):
        """BUG (analysis #2, Phase 3): a failure midway through re-keying leaves some
        blobs under the new key while imgprot.json still describes the old one."""
        crypto.set_passphrase("old pass")
        ids = [crypto.store_image(PNG + bytes([i]), "image/png") for i in range(2)]
        real, calls = os.replace, {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 3:                  # bin#1, meta#1 ok; bin#2 fails
                raise OSError("disk full")
            return real(src, dst)

        with mock.patch.object(crypto.os, "replace", flaky):
            with self.assertRaises(OSError):
                crypto.set_passphrase("new pass", "old pass")
        crypto._state["key"] = None
        self.assertTrue(crypto.unlock("old pass"))
        for i, img_id in enumerate(ids):         # every image must still open
            self.assertEqual(crypto.load_image(img_id)[0], PNG + bytes([i]))
