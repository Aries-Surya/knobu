import struct
import tempfile
import unittest
from pathlib import Path

from knobu.modules import MODULES, get
from knobu.modules.clipboard import (
    ClipboardModule,
    ClipboardStorage,
    clean_url,
    is_sensitive_clipboard,
)


class TestClipboard(unittest.TestCase):
    def test_clean_url(self):
        dirty = "https://example.com/product?id=123&utm_source=newsletter&utm_medium=email&fbclid=xyz123&keep=true"
        clean = clean_url(dirty)
        self.assertIn("id=123", clean)
        self.assertIn("keep=true", clean)
        self.assertNotIn("utm_source", clean)
        self.assertNotIn("utm_medium", clean)
        self.assertNotIn("fbclid", clean)

    def test_clean_url_non_url(self):
        plain = "Just some ordinary text with utm_source in it"
        self.assertEqual(clean_url(plain), plain)

    def test_sensitive_detection(self):
        self.assertTrue(is_sensitive_clipboard(["x-kde-passwordManagerHint", "text/plain"]))
        self.assertTrue(is_sensitive_clipboard(["application/x-keepassxc-metadata"]))
        self.assertFalse(is_sensitive_clipboard(["text/plain", "UTF8_STRING"]))

    def test_storage_add_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_clipboard.db"
            images_dir = Path(tmpdir) / "images"
            storage = ClipboardStorage(db_path=db_path, images_dir=images_dir)

            c1 = storage.add_clip("First clip")
            self.assertIsNotNone(c1)
            self.assertEqual(c1.content, "First clip")

            # Consecutive duplicate should not add a new row
            c2 = storage.add_clip("First clip")
            self.assertEqual(len(storage.get_clips()), 1)

            # Second unique clip
            storage.add_clip("Second clip")
            clips = storage.get_clips()
            self.assertEqual(len(clips), 2)
            self.assertEqual(clips[0].content, "Second clip")

            # Search filtering
            filtered = storage.get_clips(search="First")
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0].content, "First clip")

            # Pin clip
            self.assertTrue(storage.toggle_pin(c1.id))
            pinned_clips = storage.get_clips()
            self.assertEqual(pinned_clips[0].id, c1.id)
            self.assertTrue(pinned_clips[0].pinned)

            # Stats check
            stats = storage.get_stats()
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["pinned"], 1)

            # Delete clip
            storage.delete_clip(c1.id)
            self.assertEqual(len(storage.get_clips()), 1)

            # Clear all unpinned
            storage.clear_all()
            self.assertEqual(len(storage.get_clips()), 0)

    def test_image_clip_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_clipboard.db"
            images_dir = Path(tmpdir) / "images"
            storage = ClipboardStorage(db_path=db_path, images_dir=images_dir)

            # Fake PNG with valid dimensions header (640x480)
            fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 640, 480) + b"\x08\x06\x00\x00\x00"

            clip = storage.add_image_clip(fake_png)
            self.assertIsNotNone(clip)
            self.assertEqual(clip.kind, "image")
            self.assertIn("640×480", clip.preview)
            self.assertTrue(Path(clip.content).exists())

            # Stats check
            stats = storage.get_stats()
            self.assertEqual(stats["total"], 1)
            self.assertEqual(stats["images"], 1)

            # Deleting clip removes image from disk
            img_file = Path(clip.content)
            storage.delete_clip(clip.id)
            self.assertFalse(img_file.exists())

    def test_module_registration(self):
        self.assertIn(ClipboardModule, MODULES)
        mod = get("clipboard")
        self.assertEqual(mod, ClipboardModule)
        self.assertEqual(mod.id, "clipboard")
        self.assertTrue(mod.defaults["enabled"])
        self.assertEqual(mod.defaults["hotkey"], "super+v")
        self.assertEqual(mod.defaults["plain_hotkey"], "")
        self.assertTrue(mod.defaults["store_images"])
        self.assertTrue(mod.defaults["store_text"])
        self.assertTrue(mod.defaults["exclusive"])

    def test_hotkey_service_exclusive(self):
        from knobu.system import hotkeys, keys
        svc = hotkeys.HotkeyService()
        chord = keys.parse("super+v")
        fired = []
        bid = svc.register(chord, lambda: fired.append(True), exclusive=True)
        self.assertIn(bid, svc._bindings)
        self.assertTrue(svc._bindings[bid][2])
        swallowed = svc._fire(chord.key, chord.mods)
        self.assertTrue(swallowed)
        svc.unregister(bid)
        self.assertNotIn(bid, svc._bindings)


if __name__ == "__main__":
    unittest.main()
