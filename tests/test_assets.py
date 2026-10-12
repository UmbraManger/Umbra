"""The shipped icon/logo assets must stay in sync with the code that references
them. (Source art lives outside the repo; tools/make_icon.py bakes these.)"""
import os
import re
import unittest

from .helpers import BACKEND, ROOT


class IconAssetTests(unittest.TestCase):

    def test_the_exe_icon_declared_by_the_spec_exists(self):
        """PyInstaller resolves the icon relative to backend/, and build.bat
        fails outright when the file is missing."""
        with open(os.path.join(BACKEND, "Obscura.spec"), encoding="utf-8") as f:
            m = re.search(r"icon='([^']+)'", f.read())
        self.assertIsNotNone(m, "Obscura.spec must declare an icon")
        self.assertTrue(os.path.isfile(os.path.join(BACKEND, m.group(1))),
                        f"icon file missing: {m.group(1)}")

    def test_the_frontend_logo_and_favicon_exist(self):
        for rel in ("frontend/img/umbra.png", "frontend/img/favicon.png"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)),
                            f"asset missing: {rel} (re-run tools/make_icon.py)")
