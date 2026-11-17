from datetime import date, datetime

import pytest

from app import backup_lk, lk_baru


def test_id_folder():
    assert backup_lk.id_folder("https://drive.google.com/drive/folders/1K4ZVBBO1d9enuHptHfCu2RkhOL6wUMpM?usp=sharing") \
        == "1K4ZVBBO1d9enuHptHfCu2RkhOL6wUMpM"
    assert backup_lk.id_folder("https://drive.google.com/open?id=abcdefghijKLMN") == "abcdefghijKLMN"
    with pytest.raises(backup_lk.BackupError):
        backup_lk.id_folder("folder saya")


class DrivePalsu:
    """Folder + file di memori; satu file per (folder, jenis)."""

    def __init__(self):
        self.file: dict[tuple[str, str], str] = {}  # (induk, jenis) -> nama
        self.unggah: list[tuple[str, str, str]] = []  # (induk, nama, ganti)

    def folder_anak(self, sesi, induk, nama, ciri):
        return f"{induk}/{nama}"

    def cari(self, sesi, q, fields="id"):
        induk = q.split("'")[1]
        jenis = q.split("value='")[1].split("'")[0]
        return [{"id": f"id:{induk}:{jenis}"}] if (induk, jenis) in self.file else []

    def unggah_file(self, sesi, induk, nama, isi, ciri, ket, ganti=""):
        self.unggah.append((induk, nama, ganti))
        self.file[(induk, ciri["jenis"])] = nama
        return {"name": nama, "webViewLink": f"https://x/{nama}"}


@pytest.fixture
def drive(monkeypatch):
    d = DrivePalsu()
    monkeypatch.setattr(backup_lk, "folder", lambda: {"id": "ROOT", "nama": "Backup"})
    monkeypatch.setattr(backup_lk, "_sesi", lambda: object())
    monkeypatch.setattr(backup_lk, "_folder_anak", d.folder_anak)
    monkeypatch.setattr(backup_lk, "_cari", d.cari)
    monkeypatch.setattr(backup_lk, "_unggah", d.unggah_file)
    monkeypatch.setattr(backup_lk, "csv_week", lambda sesi, week: b"isi")
    monkeypatch.setattr(lk_baru, "sesi_hari", lambda: lk_baru.SESI_BAWAAN)
    monkeypatch.setattr(lk_baru, "daftar_week", lambda refresh=False: [5])
    return d


def test_akhir_sesi(monkeypatch):
    monkeypatch.setattr(lk_baru, "sesi_hari", lambda: lk_baru.SESI_BAWAAN)
    hari = [backup_lk.akhir_sesi(date(2026, 11, 16 + i)) for i in range(7)]  # Sen..Min
    assert hari == [None, None, 1, None, None, 2, 2]


def test_senin_hanya_mingguan(drive):
    r = backup_lk.jalankan("otomatis", 5, datetime(2026, 11, 16, 9, 12), "otomatis")
    assert drive.unggah == [("ROOT/WEEK 5", "WEEK 5 - Mingguan - 2026-11-16 0912.csv", "")]
    assert r["file"][0]["jenis"] == "mingguan"


def test_selasa_sesudah_mingguan_dilewati(drive):
    backup_lk.jalankan("otomatis", 5, datetime(2026, 11, 16, 9, 12), "otomatis")
    r = backup_lk.jalankan("otomatis", 5, datetime(2026, 11, 17, 9, 0), "otomatis")
    assert r["file"] == [] and "bukan hari terakhir" in r["lewati"]
    assert len(drive.unggah) == 1


def test_rabu_masuk_sesi1_dan_cutoff_kedua_menimpa(drive):
    backup_lk.jalankan("otomatis", 5, datetime(2026, 11, 16, 9, 12), "otomatis")
    backup_lk.jalankan("otomatis", 5, datetime(2026, 11, 18, 9, 0), "otomatis")
    backup_lk.jalankan("otomatis", 5, datetime(2026, 11, 18, 20, 0), "otomatis")
    assert drive.unggah[1] == ("ROOT/WEEK 5/Sesi 1", "WEEK 5 - Sesi 1 - 2026-11-18 0900.csv", "")
    assert drive.unggah[2] == ("ROOT/WEEK 5/Sesi 1", "WEEK 5 - Sesi 1 - 2026-11-18 2000.csv", "id:ROOT/WEEK 5/Sesi 1:sesi")


def test_cutoff_pertama_di_sabtu_isi_mingguan_dan_sesi2(drive):
    backup_lk.jalankan("otomatis", 5, datetime(2026, 11, 21, 8, 0), "otomatis")
    assert [i for i, _, _ in drive.unggah] == ["ROOT/WEEK 5", "ROOT/WEEK 5/Sesi 2"]


def test_week_lama_yang_sudah_diganti_nama(drive):
    """Cutoff Senin dini hari tercatat WEEK 4, lalu tab itu jadi WEEK 5."""
    r = backup_lk.jalankan("otomatis", 4, datetime(2026, 11, 16, 1, 52), "otomatis")
    assert r["week"] == 5 and drive.unggah[0][0] == "ROOT/WEEK 5"


def test_manual_pilih_tujuan(drive):
    backup_lk.jalankan("sesi1", 5, datetime(2026, 11, 20, 8, 0), "manual")
    backup_lk.jalankan("mingguan", 5, datetime(2026, 11, 20, 8, 0), "manual")
    assert [(i, n) for i, n, _ in drive.unggah] == [
        ("ROOT/WEEK 5/Sesi 1", "WEEK 5 - Sesi 1 - 2026-11-20 0800 (manual).csv"),
        ("ROOT/WEEK 5", "WEEK 5 - Mingguan - 2026-11-20 0800 (manual).csv"),
    ]


def test_susun_slot(monkeypatch):
    monkeypatch.setattr(lk_baru, "sesi_hari", lambda: lk_baru.SESI_BAWAAN)

    def f(nama, jenis, sesi, cutoff, week="5"):
        return {"name": nama, "appProperties": {"week": week, "jenis": jenis, "sesi": sesi, "cutoff": cutoff}}

    files = [f("m", "mingguan", "", "2026-11-16 01:52"), f("s1", "sesi", "1", "2026-11-18 20:00"),
             f("lama", "sesi", "2", "2026-11-14 09:00", "4")]
    folders = [{"id": "W5", "appProperties": {"week": "5", "jenis": "week"}},
               {"id": "S1", "appProperties": {"week": "5", "jenis": "sesi", "sesi": "1"}}]
    out = backup_lk.susun(files, folders, 5, date(2026, 11, 19))
    assert [w["week"] for w in out] == [5, 4]
    w5 = out[0]
    assert [(x["kunci"], x["target"]) for x in w5["slot"]] == [
        ("mingguan", "2026-11-16"), ("sesi1", "2026-11-18"), ("sesi2", "2026-11-21")]
    assert [x["file"]["nama"] if x["file"] else None for x in w5["slot"]] == ["m", "s1", None]
    assert w5["slot"][1]["link"].endswith("/S1") and w5["link"].endswith("/W5")
    assert out[1]["slot"][2]["target"] == "2026-11-14" and out[1]["slot"][2]["file"]["nama"] == "lama"
