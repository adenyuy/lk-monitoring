from app import proteksi


def _sh(i, judul, *ket):
    return {"properties": {"sheetId": i, "title": judul}, "protectedRanges": [{"description": k} for k in ket]}


def test_rencana_proteksi_judul():
    req = proteksi.rencana([_sh(1, "WEEK 4"), _sh(2, "Log Komunikasi"), _sh(3, "Log Progres"),
                            _sh(4, "WEEK 3", proteksi.KETERANGAN), _sh(5, "WEEK lama"), _sh(6, "Forum")])
    pr = [r["addProtectedRange"]["protectedRange"] for r in req]
    assert [(p["range"]["sheetId"], p["range"]["endRowIndex"]) for p in pr] == [(1, 3), (2, 2)]
    assert all(p["warningOnly"] and "startColumnIndex" not in p["range"] for p in pr)


def test_pastikan_sekali_per_tab(monkeypatch):
    kirim = []

    class Ss:
        def fetch_sheet_metadata(self, params):
            return {"sheets": [_sh(1, "WEEK 4"), _sh(2, "Log Komunikasi")]}

        def batch_update(self, body):
            kirim.append(body)

    monkeypatch.setattr(proteksi, "_sudah", set())
    assert proteksi.pastikan(Ss()) == 2
    assert proteksi.pastikan(Ss()) == 0 and len(kirim) == 1
