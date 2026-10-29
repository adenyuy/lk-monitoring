"""Bantuan tes LK: baris contoh di tes ditulis mulai kolom B dengan susunan kolom LK lama (sebelum kolom
J "Status Komunikasi (bantuan)" dan K "Waktu Tunggu" disisipkan). Posisi kolom tetap dideteksi dari judul."""

from app import sheets

ISIAN = ["A1. Alasan Progress Fisik Belum 50%", "A.2. Tindak Lanjut", "B1. Alasan Belum Submit 50%",
         "B2. Tindak Lanjut", "C1. Alasan Belum Reviu 50%", "C2. Tindak Lanjut"]
JUDUL_LAMA = ["No", "Nama PIC", "NPSN", "Nama Sekolah", "Kab/Kota", "Fasilitator", "No Fasil", "Prioritas",
              "Status Komunikasi", "% Progress Fisik Baseline", "Status Submit 50% Baseline",
              "Status Reviu 50% Baseline", "% Progress Fisik ", "Status Submit 50% ", "Status Reviu 50% "] + ISIAN * 2
KOL = sheets.parse_kolom(JUDUL_LAMA)


def parse(rows):
    """Baris mulai kolom B (tanpa kolom No) -> Sekolah."""
    return sheets.parse_lk([[""] + list(r) for r in rows], KOL)
