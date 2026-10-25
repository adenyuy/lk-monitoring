from app import db


def test_tabel_dibuat():
    names = {r["name"] for r in db.connect().execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"settings", "sends", "chat_status", "cutoff_runs"} <= names


def test_setting_simpan_baca_hapus():
    assert db.get_setting("x", "default") == "default"
    db.set_setting("x", {"batas": 40, "akhir_pekan": False})
    assert db.get_setting("x") == {"batas": 40, "akhir_pekan": False}
    db.set_setting("x", 45)
    assert db.get_setting("x") == 45
    db.delete_setting("x")
    assert db.get_setting("x") is None


def test_transaksi_rollback_saat_error():
    try:
        with db.tx() as c:
            c.execute(
                "INSERT INTO sends(tanggal, waktu, sesi, nama_fasil, nomor, hash_pesan, status) "
                "VALUES('2026-10-27','t',1,'A','62','h','terkirim')"
            )
            raise RuntimeError("gagal")
    except RuntimeError:
        pass
    assert db.connect().execute("SELECT COUNT(*) FROM sends").fetchone()[0] == 0
