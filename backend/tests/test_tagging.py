from app import tagging


def test_warna_tidak_pernah_turun():
    assert tagging.perlu_ditulis(None, "kuning")
    assert tagging.perlu_ditulis("kuning", "hijau")
    assert not tagging.perlu_ditulis("hijau", "kuning")
    assert not tagging.perlu_ditulis("hijau", "hijau")
    assert tagging.perlu_ditulis("kuning", "merah")
    assert not tagging.perlu_ditulis("merah", "hijau")


def test_warna_dari_centang():
    assert tagging.warna_kirim("read") == "hijau"
    assert tagging.warna_kirim("delivered") == "hijau"
    assert tagging.warna_kirim("sent") == "kuning"


def test_mati_saat_test():
    assert not tagging.aktif()


def test_tulis_ke_baris_fasil(monkeypatch):
    dikirim = {}

    class SS:
        def batch_update(self, body):
            dikirim.update(body)

        def values_batch_get(self, ranges):
            return {"valueRanges": [{"values": [["https://wa.me/6281200000001"]]} for _ in ranges]}

    class GC:
        def open_by_key(self, _):
            return SS()

    monkeypatch.setattr(tagging, "_baris_milik", lambda: (77, {"6281200000001": [5]}))
    monkeypatch.setattr(tagging, "gspread_client", lambda: GC())
    assert tagging.tulis("6281200000001", "hijau")
    rng = dikirim["requests"][0]["repeatCell"]["range"]
    assert rng == {"sheetId": 77, "startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 1, "endColumnIndex": 3}
    assert not tagging.tulis("6289999999999", "hijau")  # bukan fasil petugas ini


def test_lewati_bila_baris_bergeser(monkeypatch):
    class SS:
        def batch_update(self, body):
            raise AssertionError("tidak boleh menulis")

        def values_batch_get(self, ranges):
            return {"valueRanges": [{"values": [["6289999999999"]]} for _ in ranges]}

    class GC:
        def open_by_key(self, _):
            return SS()

    monkeypatch.setattr(tagging, "_baris_milik", lambda: (77, {"6281200000001": [5]}))
    monkeypatch.setattr(tagging, "gspread_client", lambda: GC())
    assert not tagging.tulis("6281200000001", "hijau")
