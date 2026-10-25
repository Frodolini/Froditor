import codecs
import os
import stat
import tempfile
import unittest

from froditor import fileio
from froditor.settings import Settings


class FileIOTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name="test.txt"):
        return os.path.join(self.dir.name, name)

    def write_bytes(self, data, name="test.txt"):
        with open(self.path(name), "wb") as f:
            f.write(data)
        return self.path(name)

    def test_utf8_roundtrip(self):
        path = self.path()
        fileio.write_text(path, "Hei på deg, æøå ÆØÅ ✓\n")
        doc = fileio.read_text(path)
        self.assertEqual(doc.text, "Hei på deg, æøå ÆØÅ ✓\n")
        self.assertEqual(doc.encoding, "utf-8")
        self.assertFalse(doc.converted)

    def test_windows_1252_is_read_and_converted(self):
        path = self.write_bytes("Blåbærsyltetøy".encode("cp1252"))
        doc = fileio.read_text(path)
        self.assertEqual(doc.text, "Blåbærsyltetøy")
        self.assertEqual(doc.encoding, "cp1252")
        self.assertTrue(doc.converted)
        self.assertEqual(doc.save_encoding, "utf-8")

    def test_bom_is_kept(self):
        path = self.write_bytes(codecs.BOM_UTF8 + "æ\n".encode())
        doc = fileio.read_text(path)
        self.assertEqual(doc.text, "æ\n")
        fileio.write_text(path, doc.text + "ø", doc.save_encoding, doc.newline)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), codecs.BOM_UTF8 + "æ\nø".encode())

    def test_utf16_with_bom(self):
        path = self.write_bytes("Hei\r\nå".encode("utf-16"))
        doc = fileio.read_text(path)
        self.assertEqual(doc.text, "Hei\nå")
        self.assertEqual(doc.newline, "\r\n")
        self.assertTrue(doc.converted)

    def test_crlf_is_preserved(self):
        path = self.write_bytes(b"linje 1\r\nlinje 2\r\n")
        doc = fileio.read_text(path)
        self.assertEqual(doc.text, "linje 1\nlinje 2\n")
        self.assertEqual(doc.newline, "\r\n")
        fileio.write_text(path, doc.text + "linje 3", doc.save_encoding, doc.newline)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"linje 1\r\nlinje 2\r\nlinje 3")

    def test_binary_is_refused(self):
        path = self.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        with self.assertRaises(fileio.BinaryFileError):
            fileio.read_text(path)

    def test_permissions_are_kept(self):
        path = self.write_bytes(b"x")
        os.chmod(path, 0o640)
        fileio.write_text(path, "y")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o640)
        self.assertEqual(os.listdir(self.dir.name), ["test.txt"])  # ingen mellombelse filer att

    def test_symlink_is_followed(self):
        target = self.write_bytes(b"gamal", "mål.txt")
        link = self.path("lenkje.txt")
        os.symlink(target, link)
        fileio.write_text(link, "ny")
        self.assertTrue(os.path.islink(link))
        with open(target, encoding="utf-8") as f:
            self.assertEqual(f.read(), "ny")


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.dir.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self.old

    def test_roundtrip_and_bad_values(self):
        settings = Settings(wrap=False, font="Monospace 16")
        settings.save()
        self.assertEqual(Settings.load(), settings)
        with open(Settings.path(), "w") as f:
            f.write('{"wrap": "ja", "width": 1000}')
        loaded = Settings.load()
        self.assertTrue(loaded.wrap)  # ugyldig verdi → standard
        self.assertEqual(loaded.width, 1000)
        with open(Settings.path(), "w") as f:
            f.write("øydelagd")
        self.assertEqual(Settings.load(), Settings())


if __name__ == "__main__":
    unittest.main()
