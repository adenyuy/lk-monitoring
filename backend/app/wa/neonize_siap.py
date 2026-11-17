"""Persiapan sebelum neonize diimpor.

neonize mengimpor `python-magic` untuk menebak jenis file media. Di Mac, python-magic butuh libmagic (dari Homebrew)
yang biasanya tidak terpasang, sehingga neonize gagal dimuat. Aplikasi hanya mengirim dan membaca teks, jadi bila
libmagic tidak ada, dipakai pengganti sederhana yang menebak dari beberapa byte pertama file.
"""

import sys
import types

_TANDA = [
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
    (b"%PDF", "application/pdf"),
    (b"OggS", "audio/ogg"),
    (b"ID3", "audio/mpeg"),
    (b"PK\x03\x04", "application/zip"),
]


def tebak(data: bytes, mime: bool = True) -> str:
    awal = bytes(data[:16])
    if awal[:4] == b"RIFF" and awal[8:12] == b"WEBP":
        return "image/webp"
    if awal[4:8] == b"ftyp":
        return "video/mp4"
    for tanda, jenis in _TANDA:
        if awal.startswith(tanda):
            return jenis
    return "application/octet-stream"


def _dari_file(path, mime: bool = True) -> str:
    with open(path, "rb") as f:
        return tebak(f.read(16), mime)


def siapkan() -> None:
    """Pasang pengganti `magic` bila python-magic tidak bisa dimuat (mis. Mac tanpa libmagic)."""
    if "magic" in sys.modules:
        return
    try:
        import magic  # noqa: F401
    except Exception:
        m = types.ModuleType("magic")
        m.from_buffer = tebak  # type: ignore[attr-defined]
        m.from_file = _dari_file  # type: ignore[attr-defined]
        m.PENGGANTI = True  # type: ignore[attr-defined]
        sys.modules["magic"] = m
