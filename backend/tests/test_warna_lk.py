from app import todo, warna_lk as w
from app.lk_baru import Sekolah, Tata


def test_warna_komponen_sama_dengan_aturan_lama():
    assert w.warna_komponen("lp", "Sudah") is w.HIJAU
    assert w.warna_komponen("lp", "Belum") is w.MERAH
    assert w.warna_komponen("lp_rev", "Belum Due") is w.ABU
    assert w.warna_komponen("lp_rev", "-") is w.ABU
    assert w.warna_komponen("lp_rev", "Dikembalikan") is w.MERAH
    assert w.warna_komponen("lp_rev", "Revisi") is w.OREN
    assert w.warna_komponen("l50", "Belum TTD Koor") is w.OREN
    assert w.warna_komponen("mg", "3/5") is w.MERAH
    assert w.warna_komponen("mg", "5/5") is w.HIJAU
    assert w.warna_komponen("progres", 0.3) is w.MERAH
    assert w.warna_komponen("progres", 0.75) is w.OREN
    assert w.warna_komponen("progres", 1) is w.HIJAU
    assert w.warna_komponen("progres", 1.0033) is w.HIJAU  # 100,33%
    assert w.warna_isian("progres", 1.0033, "") is w.ISI_SELESAI
    assert w.warna_komponen("progres", "80%") is w.OREN
    assert w.warna_komponen("progres", "") is w.POLOS
    assert w.warna_komponen("bku", "") is w.POLOS
    assert w.warna_tunggu(4) is w.MERAH_TEBAL
    assert w.warna_tunggu(3) is w.POLOS
    assert w.warna_tunggu("") is w.POLOS


def test_warna_isian():
    assert w.warna_isian("lp", "Sudah", todo.SELESAI) is w.ISI_SELESAI
    assert w.warna_isian("lp", "Sudah", "isian petugas") is w.ISI_SELESAI
    assert w.warna_isian("lp_rev", "Belum Due", todo.DUE) is w.ISI_ABU
    assert w.warna_isian("mg", "2/5", todo.BERJALAN) is w.ISI_OTOMATIS
    assert w.warna_isian("l100", "Belum", "Menunggu Lap. 50%") is w.ISI_OTOMATIS
    # pilihan petugas yang kebetulan diawali "Menunggu" tidak abu-abu
    assert w.warna_isian("mg", "2/5", "Menunggu pencairan") is w.ISI_POLOS
    assert w.warna_isian("mg", "2/5", "") is w.ISI_POLOS


def _sekolah(baris, **nilai):
    return Sekolah(baris, "Ani", "1", "SD", "", "", "", "", "", "", "", "", "", "", nilai=nilai,
                   tunggu={"lp_rev": 5.0}, isian={1: {"lp": (todo.SELESAI, todo.SELESAI)}})


def test_format_baris():
    t = Tata(identitas={"npsn": 0}, komponen={"lp": 1}, tunggu={"lp_rev": 2}, isian={1: {"lp": (3, 4)}}, lebar=5)
    peta = w.peta_kolom(t)
    f = [x["userEnteredFormat"] for x in w.format_baris(_sekolah(4, lp="Sudah"), peta, 1, 4)]
    assert f == [w.HIJAU, w.MERAH_TEBAL, w.ISI_SELESAI, w.ISI_SELESAI]



def test_rencana_tulis_hanya_yang_berubah():
    grid = [(4, "1", ["A", "B", "C"]), (5, "2", ["A", "B", "C"]), (6, "3", ["A", "X", "C"]),
            (7, "4", ["A", "B", "C"]), (8, "5", ["A", "B", "C"])]
    lama = {"1": ["A", "B", "C"], "2": ["A", "B", "C"], "3": ["A", "B", "C"], "5": ["A", "B", "Z"]}
    # baris 6: hanya kolom tengah; 7: sekolah baru -> semua kolom; 8: kolom terakhir
    assert w.rencana_tulis(grid, lama, 10) == [(6, 11, 11, 1), (7, 10, 12, 1), (8, 12, 12, 1)]
    assert w.rencana_tulis(grid, {}, 10) == [(4, 10, 12, 5)]


def test_warnai_semua_lalu_hanya_selisih(monkeypatch, tmp_path):
    t = Tata(identitas={"npsn": 0}, komponen={"lp": 1}, tunggu={"lp_rev": 2}, isian={1: {"lp": (3, 4)}}, lebar=5)
    req, meta = [], {"dm": []}

    class Ws:
        id = 9

    class Ss:
        def worksheet(self, nama):
            return Ws()

        def batch_update(self, body):
            for r in body["requests"]:
                if "createDeveloperMetadata" in r:
                    meta["dm"] = [r["createDeveloperMetadata"]["developerMetadata"]]
                elif "deleteDeveloperMetadata" not in r:
                    req.append(r)

        def fetch_sheet_metadata(self, params):
            return {"sheets": [{"properties": {"sheetId": 9}, "conditionalFormats": [{}, {}],
                                "developerMetadata": meta["dm"]}]}

    from app import paths

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    monkeypatch.setattr(w.lk_baru, "_ss", lambda: Ss())
    monkeypatch.setattr(w.lk_baru, "tata", lambda week: t)
    semua = [_sekolah(5, lp="Belum"), _sekolah(4, lp="Sudah"), _sekolah(9, lp="-")]
    semua[1].npsn, semua[2].npsn = "2", "3"
    hasil = w.warnai_semua(4, semua)
    uc = [r["updateCells"] for r in req if "updateCells" in r]
    assert [(u["start"]["rowIndex"], len(u["rows"])) for u in uc] == [(3, 2), (8, 1)]
    assert uc[0]["fields"] == w.FIELDS
    hapus = [r["deleteConditionalFormatRule"]["index"] for r in req if "deleteConditionalFormatRule" in r]
    assert hapus == [1, 0] and hasil["semua"] == 1 and hasil["sel"] == 12

    # cutoff berikutnya: satu sekolah berubah status -> hanya selnya yang dikirim
    req.clear()
    semua[0].nilai["lp"] = "Sudah"
    hasil = w.warnai_semua(4, semua)
    uc = [r["updateCells"] for r in req if "updateCells" in r]
    assert hasil["semua"] == 0 and len(uc) == 1 and uc[0]["start"] == {"sheetId": 9, "rowIndex": 4, "columnIndex": 1}

    # token di sheet berbeda (cutoff dari laptop lain) -> tulis semua lagi
    req.clear()
    meta["dm"] = [{"metadataKey": w.KUNCI_META, "metadataValue": "lain"}]
    assert w.warnai_semua(4, semua)["semua"] == 1


def test_format_ringkas():
    # false/tanpa latar tidak dikirim (FIELDS mengembalikannya ke bawaan)
    assert w.POLOS == {"textFormat": {"foregroundColor": w.TEKS_DASAR}}
    assert w.ISI_SELESAI["textFormat"]["italic"] is True and "bold" not in w.ISI_SELESAI["textFormat"]


def test_kiriman_dibatasi_jumlah_sel(monkeypatch, tmp_path):
    isian = {1: {k: (10 + 2 * i, 11 + 2 * i) for i, k in enumerate(["lp", "lp_rev", "progres", "mg"])}}
    t = Tata(identitas={"npsn": 0}, komponen={"lp": 1, "lp_rev": 2, "progres": 3, "mg": 4}, tunggu={},
             isian=isian, lebar=18)
    kiriman = []

    class Ws:
        id = 9

    class Ss:
        def worksheet(self, nama):
            return Ws()

        def batch_update(self, body):
            n = sum(len(r["updateCells"]["rows"]) * len(r["updateCells"]["rows"][0]["values"])
                    for r in body["requests"] if "updateCells" in r)
            if n:
                kiriman.append(n)

        def fetch_sheet_metadata(self, params):
            return {"sheets": [{"properties": {"sheetId": 9}}]}

    from app import paths

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    monkeypatch.setattr(w, "BATAS_SEL", 100)
    monkeypatch.setattr(w.lk_baru, "_ss", lambda: Ss())
    monkeypatch.setattr(w.lk_baru, "tata", lambda week: t)
    semua = [_sekolah(4 + i, lp="Sudah") for i in range(50)]
    for i, s in enumerate(semua):
        s.npsn = str(i)
    w.warnai_semua(4, semua)
    assert sum(kiriman) == 50 * 17 and max(kiriman) <= 100 and len(kiriman) == 10  # 5 baris x 17 kolom
