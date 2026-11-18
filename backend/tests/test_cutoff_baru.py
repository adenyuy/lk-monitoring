import pandas as pd
import pytest
import requests

from app import cutoff_baru, google_auth


def _df(**extra):
    base = {"NPSN": "123", "Nama Sekolah": "SD Uji", "Bulanan Due": "3", "Bulanan Terkirim": "2"}
    return pd.DataFrame([{**base, **extra}])


def test_bku_bpp_dari_kolom_bulanan():
    x = cutoff_baru.olah(_df(**{"Bulanan BKU Terkirim": "2", "Bulanan BPP Terkirim": "3"}))["123"]
    assert x["BKU"] == "2/3" and x["BPP"] == "3/3"


def test_bku_bpp_belum_due_dan_tanpa_target():
    x = cutoff_baru.olah(_df(**{"Bulanan Due": "Belum Due", "Bulanan BKU Terkirim": "0", "Bulanan BPP Terkirim": "0"}))
    assert x["123"]["BKU"] == "Belum Due"
    y = cutoff_baru.olah(_df(**{"Bulanan Due": "0", "Bulanan BKU Terkirim": "0", "Bulanan BPP Terkirim": "0"}))
    assert y["123"]["BPP"] == "-"


def test_tanpa_kolom_bku_tidak_diisi():
    x = cutoff_baru.olah(_df())["123"]
    assert "BKU" not in x and "BPP" not in x


def test_klien_coba_ulang_saat_koneksi_putus(monkeypatch):
    panggil = {"n": 0}

    def gagal_dua_kali(self, *a, **kw):
        panggil["n"] += 1
        if panggil["n"] <= 2:
            raise requests.exceptions.ConnectionError("Connection aborted.")
        return "ok"

    monkeypatch.setattr(google_auth.BackOffHTTPClient, "request", gagal_dua_kali)
    monkeypatch.setattr(google_auth.time, "sleep", lambda s: None)
    klien = google_auth._KlienUlang.__new__(google_auth._KlienUlang)
    assert klien.request("post", "x") == "ok" and panggil["n"] == 3


def test_klien_menyerah_setelah_batas(monkeypatch):
    def selalu_gagal(self, *a, **kw):
        raise requests.exceptions.ConnectionError("Connection aborted.")

    monkeypatch.setattr(google_auth.BackOffHTTPClient, "request", selalu_gagal)
    monkeypatch.setattr(google_auth.time, "sleep", lambda s: None)
    klien = google_auth._KlienUlang.__new__(google_auth._KlienUlang)
    with pytest.raises(requests.exceptions.ConnectionError):
        klien.request("post", "x")


class _SsPalsu:
    def __init__(self, judul, data):
        self.judul, self.data, self.tulis = judul, data, []

    def values_get(self, rng, params=None):
        return {"values": [self.judul] if rng.endswith("3") else self.data}

    def values_update(self, rng, params=None, body=None):
        self.tulis.append((rng, body["values"]))


def test_cutoff_hanya_menulis_kolom_komponen(monkeypatch):
    from app import lk_baru

    judul = ["PIC", "NPSN", "Nama Sekolah", "Fasilitator", "Status Laporan Pendahuluan",
             "Waktu Tunggu Reviu Laporan Pendahuluan", "Reviu Laporan Pendahuluan"]
    data = [["Petugas A", "123", "SD Lama", "Fasil Lama", "Belum", "", "-"]]
    ss = _SsPalsu(judul, data)
    t = lk_baru.Tata(identitas={"petugas": 0, "npsn": 1, "nama": 2, "fasil": 3}, komponen={"lp": 4, "lp_rev": 6},
                     tunggu={"lp_rev": 5}, isian={}, lebar=7)
    monkeypatch.setattr(lk_baru, "tata", lambda week, refresh=False: t)
    monkeypatch.setattr(lk_baru, "_ss", lambda: ss)
    df = pd.DataFrame([
        {"NPSN": "123", "Nama Sekolah": "SD Baru Ganti Nama", "Fasilitator": "Fasil Lain",
         "Pendahuluan - Status Kirim": "Sudah Dikirim", "Pendahuluan - Status Reviu": "Disetujui",
         "Hari Verif Pendahuluan": "2"},
        {"NPSN": "999", "Nama Sekolah": "SD Tambahan", "Fasilitator": "Fasil X",
         "Pendahuluan - Status Kirim": "Belum Dikirim", "Pendahuluan - Status Reviu": "Belum Dikirim",
         "Hari Verif Pendahuluan": ""}])
    monkeypatch.setattr(cutoff_baru, "baca", lambda data, nama: df)
    rc = cutoff_baru.siapkan(b"", "x.csv", 3)
    assert rc.kol_awal == 4
    assert rc.baris == [["Sudah", 2.0, "Sudah"]]  # identitas (PIC, nama, fasil) tidak ikut blok komponen
    assert [(p["npsn"], p["kunci"], p["lama"], p["baru"]) for p in rc.pemetaan] == [
        ("123", "nama", "SD Lama", "SD Baru Ganti Nama"), ("123", "fasil", "Fasil Lama", "Fasil Lain")]
    assert rc.ringkasan["pemetaan_sekolah"] == 1
    assert {b["kolom"] for b in rc.ringkasan["berubah"]} == {"Status Laporan Pendahuluan",
                                                              "Waktu Tunggu Reviu Laporan Pendahuluan",
                                                              "Reviu Laporan Pendahuluan"}
    assert rc.tambah[0][1] == "999" and rc.tambah[0][2] == "SD Tambahan"  # sekolah baru tetap lengkap


KOLOM_PETA = {"nama": 0, "ptn": 1, "koor": 2, "hp_koor": 3, "fasil": 4, "hp_fasil": 5}


def _beda(r, rusak=(), **x):
    isi = {cutoff_baru.PEMETAAN[k]: v for k, v in x.items()}
    return {p["kunci"]: p["baru"] for p in cutoff_baru.beda_pemetaan(r, {**isi, "_hp_rusak": set(rusak)}, KOLOM_PETA, set(isi))}


BARIS_PETA = ["SD A", "PTN", "Koor", "081111111111", "Fasil Lama", "082222222222"]
SAMA_PETA = dict(nama="SD A", ptn="PTN", koor="Koor", hp_koor="081111111111", fasil="Fasil Lama", hp_fasil="082222222222")


def test_pemetaan_sama_dengan_file_tidak_ada_perubahan():
    assert _beda(BARIS_PETA, **SAMA_PETA) == {}
    assert _beda(BARIS_PETA, **{**SAMA_PETA, "hp_fasil": "6282222222222"}) == {}  # nomor sama, beda penulisan


def test_pemetaan_mengikuti_file_termasuk_nomor_orang_sama():
    x = {**SAMA_PETA, "nama": "SD a", "koor": "Koor Baru", "hp_koor": "083333333333", "hp_fasil": "084444444444"}
    assert _beda(BARIS_PETA, **x) == {"nama": "SD a", "koor": "Koor Baru", "hp_koor": "083333333333", "hp_fasil": "084444444444"}


def test_pemetaan_nilai_kosong_di_file_ikut_kosong():
    assert _beda(BARIS_PETA, **{**SAMA_PETA, "fasil": "", "hp_fasil": ""}) == {"fasil": "", "hp_fasil": ""}


def test_pemetaan_kolom_tidak_dipakai_tidak_menyentuh_lk():
    x = {"Fasilitator": "", "No HP Fasilitator": "", "_hp_rusak": set()}
    assert cutoff_baru.beda_pemetaan(BARIS_PETA, x, KOLOM_PETA, set()) == []


def test_judul_pemetaan_abaikan_kolom_hilang_atau_kosong_total():
    df = pd.DataFrame([{"Fasilitator": "Fasil Baru", "PTN": " "}, {"Fasilitator": "", "PTN": ""}])
    assert cutoff_baru.judul_pemetaan(df) == {"Fasilitator"}


def test_pemetaan_nomor_rusak_orang_sama_tetap():
    x = {**SAMA_PETA, "hp_fasil": ""}
    assert _beda(BARIS_PETA, rusak={"No HP Fasilitator"}, **x) == {}


def test_pemetaan_nomor_rusak_orang_baru_dikosongkan():
    x = {**SAMA_PETA, "fasil": "Fasil Baru", "hp_fasil": ""}
    assert _beda(BARIS_PETA, rusak={"No HP Fasilitator"}, **x) == {"fasil": "Fasil Baru", "hp_fasil": ""}


def test_olah_menandai_nomor_rusak_bukan_nomor_kosong():
    x = cutoff_baru.olah(_df(**{"No HP Fasilitator": "6,28E+12", "No HP Koordinator": ""}))["123"]
    assert x["_hp_rusak"] == {"No HP Fasilitator"}


def test_tulis_pemetaan_mengikuti_baris_npsn_terkini():
    from types import SimpleNamespace as S

    class Ss:
        kirim = []

        def values_get(self, rng, params=None):
            return {"values": [[999.0], [], ["123"]]}

        def values_batch_update(self, body):
            self.kirim += body["data"]

    isi = [{"npsn": "123", "kunci": "fasil", "baru": "Fasil Baru"}, {"npsn": "404", "kunci": "fasil", "baru": "X"}]
    assert cutoff_baru.tulis_pemetaan(Ss(), "WEEK 5", S(identitas={"npsn": 1, "fasil": 3}), isi) == 1
    assert Ss.kirim == [{"range": "'WEEK 5'!D6", "values": [["Fasil Baru"]]}]  # data mulai baris 4, NPSN 123 di baris 6


def test_rencana_pemetaan_log_kom_ikut_judul_kolom():
    from types import SimpleNamespace as S

    semua = [S(npsn="1", nama="SD 1", ptn="P", koor="Koor Baru", fasil="Fasil Baru"), S(npsn="2", nama="SD 2", ptn="", koor="K", fasil="F")]
    judul = ["PIC", "NPSN", "Nama Sekolah", "PTN", "Koordinator", "Fasilitator"]
    rows = [["Ani", 1.0, "SD 1", "P", "Koor Lama", "Fasil Lama"], ["Ani", "2", "sd 2", "Q", "K", "F"], ["Ani", "3", "SD 3", "P", "K", "F"]]
    assert cutoff_baru.rencana_pemetaan_log_kom(semua, judul, rows) == [
        ("E", 3, "Koor Baru"), ("F", 3, "Fasil Baru"), ("C", 4, "SD 2"), ("D", 4, "")]
    assert cutoff_baru.rencana_pemetaan_log_kom(semua, ["PIC", "NPSN", "A", "B", "C", "D"], rows) == []


def test_rencana_log_kom_sekolah_baru_dan_pic():
    from types import SimpleNamespace as S

    semua = [S(npsn="1", petugas="Ani", nama="SD 1", ptn="P", koor="K", fasil="F"),
             S(npsn="2", petugas="Budi", nama="SD 2", ptn="P", koor="K", fasil="F"),
             S(npsn="3", petugas="Cici", nama="SD 3", ptn="Q", koor="L", fasil="G"),
             S(npsn="4", petugas="", nama="SD 4", ptn="Q", koor="L", fasil="G")]
    log_rows = [["Ani", "1"], ["", "2"], ["Dodi", 3.0]]  # NPSN bisa terbaca angka
    baru, ubah = cutoff_baru.rencana_log_kom(semua, log_rows)
    assert baru == [["", "4", "SD 4", "Q", "L", "G"]]
    assert ubah == [(4, "Budi"), (5, "Cici")]  # baris sheet mulai 3


def test_sekolah_baru_diwarnai_kuning():
    class W:
        title, id, col_count = "WEEK 4", 7, 83

    class SS:
        def __init__(self):
            self.req = []

        def batch_update(self, body):
            self.req += body["requests"]

    ss = SS()
    cutoff_baru.warnai_sekolah_baru(ss, W(), 2000, 3, 13)  # hanya kolom Informasi Sekolah A..M
    rc = ss.req[0]["repeatCell"]
    assert rc["range"] == {"sheetId": 7, "startRowIndex": 1999, "endRowIndex": 2002,
                           "startColumnIndex": 0, "endColumnIndex": 13}
    assert rc["cell"]["userEnteredFormat"]["backgroundColor"] == cutoff_baru.KUNING
    assert rc["fields"] == "userEnteredFormat.backgroundColor"


def test_baris_sekolah_mengundurkan_diri_ikut_judul():
    from types import SimpleNamespace

    s = SimpleNamespace(petugas="Ani", npsn="123", nama="SD A", angkatan="2", provinsi="Prov. X", kab="Kab. Y", kepsek="Bu Z",
                        hp_kepsek="08", ptn="PTN Q", koor="Koor", hp_koor="09", fasil="Fasil F", hp_fasil="07", bimtek="")
    judul = ["PIC", "NPSN", "Nama Sekolah", "Angkatan", "Provinsi", "Kab/Kota", "Nama Kepala Sekolah", "No HP Kepala Sekolah",
             "PTN", "Koordinator", "No HP Koordinator", "Fasilitator", "No HP Fasilitator", "Kasus", "Catatan Tambahan"]
    r = cutoff_baru.baris_mundur(judul, s, "16/11/2026")
    assert r[:3] == ["Ani", "123", "SD A"] and r[11:13] == ["Fasil F", "07"]
    assert r[13] == cutoff_baru.KASUS_HILANG and "16/11/2026" in r[14] and len(r) == len(judul)


def test_rapikan_baris_repeatcell_per_rentang_dan_warna_lama_dibuang(monkeypatch):
    # baris 4-9: baris 6, 7, 9 kehilangan format; contoh diambil dari baris 4
    rapi = {4, 5, 8}
    tf = {"foregroundColor": {"red": 1}, "foregroundColorStyle": {"rgbColor": {"red": 1}}, "bold": True}
    kiriman = []

    class Ss:
        def fetch_sheet_metadata(self, params):
            if "wrapStrategy)))))" in params["fields"]:
                return {"sheets": [{"data": [{"rowData": [
                    {"values": [{"userEnteredFormat": {"wrapStrategy": "CLIP"}}]} if b in rapi else {}
                    for b in range(4, 10)]}]}]}
            return {"sheets": [{"data": [{"rowData": [{"values": [
                {"userEnteredFormat": {"wrapStrategy": "CLIP", "textFormat": tf}}] * 3}]}]}]}

        def batch_update(self, body):
            kiriman.append(body["requests"])

    class W:
        id, col_count = 7, 3

    monkeypatch.setattr(cutoff_baru, "PERMINTAAN_FORMAT_PER_KIRIM", 4)
    assert cutoff_baru.rapikan_baris(Ss(), W(), "WEEK 4", 9) == 3
    req = [r["repeatCell"] for k in kiriman for r in k]
    assert [len(k) for k in kiriman] == [4, 2]  # 2 rentang x 3 kolom, maks 4 per kiriman
    assert sorted({(r["range"]["startRowIndex"], r["range"]["endRowIndex"]) for r in req}) == [(5, 7), (8, 9)]
    sel_tf = req[0]["cell"]["userEnteredFormat"]["textFormat"]
    assert "foregroundColor" not in sel_tf and sel_tf["foregroundColorStyle"] == {"rgbColor": {"red": 1}}
    assert sel_tf["bold"] is True


def test_tanpa_warna_lama_hanya_bila_ada_style():
    assert cutoff_baru._tanpa_warna_lama({"borders": {"top": {"color": {"red": 1}, "style": "SOLID"}}}) == \
        {"borders": {"top": {"color": {"red": 1}, "style": "SOLID"}}}
    assert cutoff_baru._tanpa_warna_lama({"color": 1, "colorStyle": 2}) == {"colorStyle": 2}


def test_pemetaan_nomor_tidak_baku_yang_sama_tidak_ditulis_ulang():
    r = ["SD A", "PTN", "Koor", "075233556", "Fasil Lama", "082222222222"]
    assert _beda(r, **{**SAMA_PETA, "hp_koor": "075233556"}) == {}
