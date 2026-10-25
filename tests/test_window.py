"""Testar vindauget utan å klikke. Krev skjerm (køyr med xvfb-run i CI)."""

import os
import tempfile
import unittest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    HAVE_DISPLAY = Gtk.init_check()
except (ImportError, ValueError):
    HAVE_DISPLAY = False


def pump():
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


@unittest.skipUnless(HAVE_DISPLAY, "treng GTK 4 og ein skjerm")
class WindowTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        os.environ["XDG_CONFIG_HOME"] = self.dir.name
        os.environ["XDG_DATA_HOME"] = self.dir.name
        GLib.set_application_name("Froditor-test")
        from froditor.settings import Settings
        from froditor.window import FroditorWindow

        self.win = FroditorWindow(settings=Settings())
        self.win.present()
        pump()
        self.addCleanup(self.win.destroy)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def test_open_edit_save(self):
        path = self.path("notat.txt")
        with open(path, "wb") as f:
            f.write(b"Hei\r\nverda\r\n")
        self.assertTrue(self.win.load_file(path))
        self.assertEqual(self.win.get_text(), "Hei\nverda\n")
        self.assertEqual(self.win.get_title(), "notat.txt – Froditor")

        self.win.buffer.insert(self.win.buffer.get_end_iter(), "frå Froditor")
        self.assertEqual(self.win.get_title(), "*notat.txt – Froditor")
        self.assertEqual(self.win.title_label.get_text(), "*notat.txt – Froditor")

        self.win.save()
        with open(path, "rb") as f:
            self.assertEqual(f.read(), "Hei\r\nverda\r\nfrå Froditor".encode())
        self.assertFalse(self.win.buffer.get_modified())
        self.assertEqual(self.win.get_title(), "notat.txt – Froditor")

    def test_missing_file_becomes_new_file(self):
        path = self.path("ny.txt")
        self.assertTrue(self.win.load_file(path))
        self.win.buffer.set_text("innhald")
        self.win.save()
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "innhald")

    def test_load_is_not_undoable(self):
        path = self.path("a.txt")
        with open(path, "w") as f:
            f.write("original")
        self.win.load_file(path)
        self.assertFalse(self.win.buffer.get_can_undo())

    def test_find_and_replace(self):
        self.win.buffer.set_text("Katt, katt og KATT. Hund.")
        self.win.show_search(replace=True)
        self.win.find_entry.set_text("katt")
        pump()
        self.assertEqual(self.win.match_label.get_text(), "3 treff")

        self.win.case_check.set_active(True)
        self.assertEqual(self.win.match_label.get_text(), "1 treff")
        self.win.case_check.set_active(False)

        self.win.replace_entry.set_text("hest")
        self.assertEqual(self.win.replace_all(), 3)
        self.assertEqual(self.win.get_text(), "hest, hest og hest. Hund.")
        self.win.buffer.undo()
        self.assertEqual(self.win.get_text(), "Katt, katt og KATT. Hund.")

        self.win.hide_search()
        self.assertFalse(self.win.search_revealer.get_reveal_child())

    def test_replace_with_text_containing_needle(self):
        self.win.buffer.set_text("a a a")
        self.win.show_search(replace=True)
        self.win.find_entry.set_text("a")
        self.win.replace_entry.set_text("aa")
        self.assertEqual(self.win.replace_all(), 3)
        self.assertEqual(self.win.get_text(), "aa aa aa")

    def test_binary_file_is_refused(self):
        path = self.path("bilete.png")
        with open(path, "wb") as f:
            f.write(b"\x89PNG\x00\x00")
        self.assertFalse(self.win.load_file(path))
        self.assertIsNone(self.win.path)

    def test_zoom_and_wrap(self):
        self.win.zoom(+2)
        self.assertEqual(self.win.settings.font, "Monospace 14")
        self.win.zoom(0)
        self.assertEqual(self.win.settings.font, "Monospace 12")
        self.win.activate_action("win.wrap", None)
        self.assertEqual(self.win.textview.get_wrap_mode(), Gtk.WrapMode.NONE)

    def test_new_ps1_gets_bom_existing_keeps_encoding(self):
        new_script = self.path("ny.ps1")
        self.win.buffer.set_text("Write-Host 'Blåbær'")
        self.assertTrue(self.win._write(new_script))
        with open(new_script, "rb") as f:
            self.assertTrue(f.read().startswith(b"\xef\xbb\xbf"))

        old_script = self.path("gamal.ps1")
        with open(old_script, "w", encoding="utf-8") as f:
            f.write("Get-Date")
        self.win.load_file(old_script)
        self.win.buffer.set_text("Get-Date -Format 'yyyy'")
        self.win.save()
        with open(old_script, "rb") as f:
            self.assertEqual(f.read(), b"Get-Date -Format 'yyyy'")

    def test_current_suffix_follows_open_file(self):
        self.assertEqual(self.win._current_suffix(), ".txt")
        self.win.load_file(self.path("skript.ps1"))
        self.assertEqual(self.win._current_suffix(), ".ps1")

    def test_close_with_unsaved_changes_asks(self):
        self.win.buffer.set_text("ulagra")
        self.assertTrue(self.win.emit("close-request"))  # stoppa: spør først
        self.assertTrue(self.win.get_visible())


if __name__ == "__main__":
    unittest.main()
