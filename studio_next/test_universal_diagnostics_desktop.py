"""Native desktop dashboard smoke test against actual local BODY API.

This tests display and data transport, NOT an actual neural audition.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from studio_next.body_desktop import IndependentStudioDesktop
from studio_next.test_body_controls import local_service


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk display is required")
class RealDesktopDiagnosticsTests(unittest.TestCase):
    def test_initial_native_tab_shows_host_measured_capability_families(self):
        import tkinter as tk
        with tempfile.TemporaryDirectory() as folder:
            with local_service(Path(folder) / "host") as (_, client):
                window=tk.Tk()
                try:
                    with patch("tkinter.messagebox.showerror", side_effect=AssertionError(
                            "Actual host UI must not silently hide diagnostic failures")):
                        view=IndependentStudioDesktop(window,client)
                        self.assertEqual(view.diagnostics_tree["columns"],
                                         ("family", "installed", "needs_setup"))
                        stop=time.monotonic()+18
                        while time.monotonic()<stop:
                            window.update()
                            if (view.diagnostic_summary.get().startswith("BODY ")
                                    and view.diagnostics_tree.get_children()):
                                break
                            time.sleep(.04)
                        summary=view.diagnostic_summary.get()
                        self.assertTrue(summary.startswith("BODY "),summary)
                        self.assertIn("creative ability unmeasured",summary)
                        self.assertGreater(len(view.diagnostics_tree.get_children()),0)
                        self.assertIn("UNMEASURED:",
                                      view.diagnostic_issues.get("1.0","end"))
                finally:
                    window.destroy()


if __name__ == "__main__":
    unittest.main()
