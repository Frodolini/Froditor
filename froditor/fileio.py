"""Lesing og skriving av tekstfiler.

Froditor les UTF-8 (med eller utan BOM), UTF-16 med BOM og eldre
Windows-filer (Windows-1252 / Latin-1). Det blir alltid lagra som UTF-8,
og linjeskiftet fila hadde (LF eller CRLF) blir teke vare på.
"""

import codecs
import os
import stat
import tempfile
from dataclasses import dataclass

UTF8 = "utf-8"
UTF8_BOM = "utf-8-sig"

ENCODING_NAMES = {
    "utf-8": "UTF-8",
    "utf-8-sig": "UTF-8 med BOM",
    "utf-16": "UTF-16",
    "cp1252": "Windows-1252",
    "latin-1": "Latin-1",
}

NEWLINE_NAMES = {
    "\n": "Linux (LF)",
    "\r\n": "Windows (CRLF)",
    "\r": "Klassisk Mac (CR)",
}


class BinaryFileError(Exception):
    """Fila ser ut til å vere ei binærfil, ikkje tekst."""


@dataclass
class Document:
    text: str
    encoding: str = UTF8
    newline: str = "\n"

    @property
    def save_encoding(self) -> str:
        """Teiknkodinga fila skal lagrast med."""
        return UTF8_BOM if self.encoding == UTF8_BOM else UTF8

    @property
    def converted(self) -> bool:
        """Sant dersom fila blir konvertert til UTF-8 ved lagring."""
        return self.encoding not in (UTF8, UTF8_BOM)


def decode(data: bytes) -> tuple[str, str]:
    """Returnerer (tekst, teiknkoding) for innhaldet i ei fil."""
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode(UTF8, "replace"), UTF8_BOM
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", "replace"), "utf-16"
    if b"\x00" in data[:8192]:
        raise BinaryFileError
    for encoding in (UTF8, "cp1252"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1"), "latin-1"


def detect_newline(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    if crlf and crlf >= lf:
        return "\r\n"
    if not lf and "\r" in text:
        return "\r"
    return "\n"


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: str) -> Document:
    with open(path, "rb") as f:
        data = f.read()
    text, encoding = decode(data)
    newline = detect_newline(text)
    return Document(normalize_newlines(text), encoding, newline)


def _current_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def write_text(path: str, text: str, encoding: str = UTF8, newline: str = "\n") -> None:
    """Skriv teksten trygt: først til ei mellombels fil, så byter vi ut originalen.

    Då blir ikkje fila øydelagd om noko går gale midt i lagringa.
    """
    if newline != "\n":
        text = text.replace("\n", newline)
    data = text.encode(encoding)

    path = os.path.realpath(os.path.abspath(path))  # skriv gjennom symbolske lenkjer
    folder = os.path.dirname(path)
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        mode = 0o666 & ~_current_umask()

    try:
        fd, tmp = tempfile.mkstemp(prefix=".froditor-", suffix=".tmp", dir=folder)
    except PermissionError:
        # Vi får ikkje lage filer i mappa, men kanskje skrive til sjølve fila.
        with open(path, "wb") as f:
            f.write(data)
        return

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
