from datetime import datetime

from app import bc_draft
from app.undangan_wag import isi_salam

KEPALA = [["BC OTOMATIS"], ["SUMBER DATA"], ["SAPAAN (WIB)", "Selamat malam"], ["TAUTAN"], ["CARA PAKAI"]]


def test_tab_fasil_hanya_baris_petugas_dan_salam_ikut_jam():
    v = KEPALA + [["PIC", "Nama Fasilitator", "Nomor WA Fasilitator", "Jumlah Sekolah", "Daftar Sekolah",
                   "BC Otomatis (Siap Salin)", "Link WhatsApp + BC"],
                  ["Petugas A", "Fasil Satu", "WA KOSONG", "2", "...", "📌 *INFO*\n\nSelamat malam, Bapak/Ibu *Fasil Satu*.", "x"],
                  ["Petugas B", "Fasil Dua", "", "1", "...", "Selamat malam, Bapak/Ibu Fasil Dua.", "x"]]
    x = bc_draft.parse_tab("BC - LP BELUM SUBMIT", v, "petugas a")
    assert x["jenis"] == "fasil" and x["judul"] == "BC Lp Belum Submit"
    assert x["pesan"] == [("Fasil Satu", "📌 *INFO*\n\nSelamat {salam}, Bapak/Ibu *Fasil Satu*.")]
    assert isi_salam(x["pesan"][0][1], datetime(2026, 11, 10, 9)).endswith("Selamat pagi, Bapak/Ibu *Fasil Satu*.")


def test_tab_koordinator_dan_format_lain():
    v = KEPALA + [["PIC Monitoring", "Koordinator PTN", "PTN", "Nomor WA Koordinator", "BC Otomatis (Siap Salin)",
                   "Link WhatsApp + BC"], ["Petugas A", "Koor X", "PTN", "08", "Halo Koor X", "x"]]
    x = bc_draft.parse_tab("BC - KOORDINATOR PTN", v, "Petugas A")
    assert x["jenis"] == "koor" and x["pesan"] == [("Koor X", "Halo Koor X")]
    assert bc_draft.parse_tab("BC - LAIN", [["judul saja"]], "Petugas A") is None


def test_salam_blast_tanpa_kata_selamat():
    t = datetime(2026, 11, 10, 14)
    assert isi_salam("{salam} Bapak/Ibu X", t) == "Selamat siang Bapak/Ibu X"
    assert isi_salam("Selamat {salam} Bapak", t) == "Selamat siang Bapak"
