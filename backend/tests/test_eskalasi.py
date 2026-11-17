from datetime import datetime

import pytest

from app import eskalasi

TIM = ["Tim Monitoring", "Tim Aplikasi", "Tim Substansi", "PMO", "Tim Penyaluran", "Tim Regulasi", "Tim PBJ", "BPMP",
       "Dinas", "Pengawas PTN"]
JUDUL = ["ID Masalah", "Sumber Masalah (asal/penyebab)", "NPSN (Sekolah Terdampak)", "Nama Sumber / Topik (opsional)",
         "Nama Sekolah", "Fasilitator", "Petugas Monitoring", "PTN", "Masalah Aktif di Sekolah Ini",
         "Keterangan Permasalahan", "Permasalahan", "Tingkat", "Evidence (Tautan Bukti)", "Tanggal Awal Permasalahan",
         "Perlu Agregasi?", *TIM, "Saran Kode Tema (otomatis)", "Kode Tema (diisi PIC)", "Jawaban Tim Terkait",
         "Status Tindak lanjut", "Tanggal Permasalahan Selesai", "Pengisi Jawaban", "Status Eskalasi (PIC)",
         "Tema Agregasi", "Tim Tujuan (otomatis dari checklist)", "Batas Waktu", "Status Waktu"]
F = [False] * 10


def baris(mid, npsn, ket, petugas="Ani", status="Belum Ditindaklanjuti", tim=None, evidence="", selesai=""):
    t = [x in (tim or []) for x in TIM]
    return [mid, "Sekolah", npsn, "", "SD " + npsn, "Fasil", petugas, "PTN X", 1, ket, "Aplikasi & Akun", "", evidence,
            46326, "Ya", *t, "T01", "", "", status, selesai, "", "Belum Dieskalasi", "tema", "", 46330, "Sisa 1"]


class SS:
    def __init__(self, data):
        self.data = data
        self.tulis = []

    def values_get(self, rng, params=None):
        if rng.startswith("'LK Eskalasi'!A4"):
            return {"values": [JUDUL] + self.data}
        if rng.startswith("'LK Eskalasi'!A"):  # cek ID setelah tulis
            awal, akhir = (int(x) for x in rng.split("!A")[1].split(":A")) if ":" in rng else (int(rng.split("!A")[1]),) * 2
            return {"values": [[self.data[n - 5][0]] if n - 5 < len(self.data) else [] for n in range(awal, akhir + 1)]}
        if rng.startswith("'Master Data'"):
            return {"values": [["999", "SD Master", "Budi", "Fasil M", "PTN M"]]}
        return {"values": []}

    def values_batch_get(self, rng, params=None):
        if rng[0].startswith("'LK Eskalasi'"):  # sidik: kolom NPSN & Keterangan
            out = []
            for r in rng:
                sel = r.split("!")[1]
                a, b = sel.split(":")
                kol = "".join(c for c in a if c.isalpha())
                i = next(j for j in range(60) if eskalasi.col_letter(j) == kol)
                n1, n2 = int(a[len(kol):]), int(b[len(kol):])
                out.append({"values": [[self.data[n - 5][i]] if n - 5 < len(self.data) and i < len(self.data[n - 5]) else []
                                       for n in range(n1, n2 + 1)]})
            return {"valueRanges": out}
        return {"valueRanges": [
            {"values": [["Aplikasi & Akun"], ["Lainnya"]]},
            {"values": [["Belum Ditindaklanjuti"], ["Proses"], ["Selesai"]]},
            {"values": [["Tingkat 2 – Reguler"], ["Tingkat 3 – Prioritas Tinggi"]]},
            {"values": [["T01", "Tema satu"], ["T02", "Tema dua"], ["", ""]]},
            {"values": [["Tim Monitoring", "Nashwa"], ["Tim Aplikasi", "Rafli"], ["CATATAN: x", "y"]]},
        ]}

    def worksheet(self, _):
        return type("W", (), {"row_count": 3004})()

    def values_batch_update(self, body):
        self.tulis.append(body)
        # terapkan ke data supaya cek ID setelah tulis lolos
        for d in body["data"]:
            sel = d["range"].split("!")[1].split(":")[0]
            n = int("".join(c for c in sel if c.isdigit()))
            kol = eskalasi.col_letter
            awal = next(i for i in range(60) if kol(i) == "".join(c for c in sel if c.isalpha()))
            while len(self.data) < n - 4:
                self.data.append([""] * len(JUDUL))
            r = self.data[n - 5]
            r += [""] * (len(JUDUL) - len(r))
            for j, v in enumerate(d["values"][0]):
                r[awal + j] = v


@pytest.fixture
def ss(monkeypatch):
    s = SS([
        baris("E-0001", "111", "Akun fasil error terus", tim=["Tim Aplikasi"],
              evidence="https://drive.google.com/file/d/abcdefghijklmnopqrstuvwxyz/view\nhttps://contoh.id/x"),
        baris("E-0007", "222", "Dana belum cair sejak lama", petugas="Budi", status="Selesai", selesai=46330),
    ])
    monkeypatch.setattr(eskalasi, "sheet_id", lambda: "x")
    monkeypatch.setattr(eskalasi, "gspread_client", lambda: type("GC", (), {"open_by_key": lambda self, _: s})())
    monkeypatch.setattr(eskalasi.schedule, "now", lambda: datetime(2026, 11, 16, 9))
    monkeypatch.setattr(eskalasi, "_peta_lk", lambda: {"333": {"npsn": "333", "nama": "SD Tiga", "petugas": "Ani",
                                                               "fasil": "Fasil T", "ptn": "PTN T"}})
    eskalasi.cache.clear()
    return s


def test_judul_dan_tim():
    pos, tim = eskalasi.parse_judul(JUDUL)
    assert tim == TIM
    assert pos["sumber"] == 1 and pos["agregasi"] == 14 and pos["kode_tema"] == 26 and pos["tim:PMO"] == 18


def test_judul_hilang():
    with pytest.raises(eskalasi.EskalasiError, match="id masalah"):
        eskalasi.parse_judul(JUDUL[1:])


def test_baca(ss):
    m = eskalasi.semua()
    assert [x["id"] for x in m] == ["E-0007", "E-0001"] or [x["id"] for x in m] == ["E-0001", "E-0007"]
    a = next(x for x in m if x["id"] == "E-0001")
    assert a["tim"] == ["Tim Aplikasi"] and a["tgl_awal"] == "2026-10-31" and a["aktif"] == 1
    assert a["foto"] == ["abcdefghijklmnopqrstuvwxyz"] and a["tautan"] == ["https://contoh.id/x"]
    assert eskalasi.daftar(["222"])[0]["tgl_selesai"] == "2026-11-04"


def test_opsi(ss):
    o = eskalasi.opsi()
    assert o["tema"] == [{"kode": "T01", "tema": "Tema satu"}, {"kode": "T02", "tema": "Tema dua"}]
    assert o["pic"] == {"Tim Monitoring": "Nashwa", "Tim Aplikasi": "Rafli"}
    assert o["tim"] == TIM


def test_sekolah_lk_lalu_master(ss):
    assert eskalasi.sekolah("333")["asal"] == "LK"
    assert eskalasi.sekolah("999") == {"npsn": "999", "nama": "SD Master", "petugas": "Budi", "fasil": "Fasil M",
                                       "ptn": "PTN M", "asal": "Master Data"}
    assert eskalasi.sekolah("000") is None


ISI = {"sumber": "Sekolah", "keterangan": "Sekolah belum bisa login aplikasi", "permasalahan": "Aplikasi & Akun",
       "tim": ["Tim Aplikasi", "BPMP"], "evidence": ["abcdefghijklmnopqrstuvwxyz"]}


def test_catat_dua_sekolah_id_berurutan(ss):
    h = eskalasi.catat(ISI, ["333", "999"], "Ani")
    assert [x["id"] for x in h] == ["E-0008", "E-0009"] and [x["baris"] for x in h] == [7, 8]
    r = ss.data[2]
    pos, _ = eskalasi.parse_judul(JUDUL)
    assert r[pos["nama"]] == "SD Tiga" and r[pos["petugas"]] == "Ani" and r[pos["ptn"]] == "PTN T"
    assert r[pos["tim:BPMP"]] is True and r[pos["tim:PMO"]] is False
    assert r[pos["evidence"]] == "https://drive.google.com/file/d/abcdefghijklmnopqrstuvwxyz/view"
    assert r[pos["tgl_awal"]] == 46342 and r[pos["status"]] == "Belum Ditindaklanjuti"
    assert ss.data[3][pos["petugas"]] == "Budi"
    # kolom berumus tidak pernah ditulis
    rng = " ".join(d["range"] for b in ss.tulis for d in b["data"])
    for f in ("aktif", "saran_tema", "tema", "tim_tujuan", "batas", "status_waktu", "tgl_selesai"):
        assert f"!{eskalasi.col_letter(pos[f])}7" not in rng


def test_catat_tanpa_npsn_butuh_topik(ss):
    with pytest.raises(eskalasi.EskalasiError, match="NPSN"):
        eskalasi.catat(ISI, [], "Ani")
    with pytest.raises(eskalasi.EskalasiError, match="Topik"):
        eskalasi.catat({**ISI, "sumber": "Umum/Sistem"}, [], "Ani")
    h = eskalasi.catat({**ISI, "sumber": "Umum/Sistem", "topik": "Server lambat"}, [], "Ani")
    assert h[0]["npsn"] == "" and ss.data[2][6] == "Ani"


def test_catat_npsn_tidak_dikenal(ss):
    with pytest.raises(eskalasi.EskalasiError, match="000"):
        eskalasi.catat(ISI, ["000"], "Ani")
    assert ss.tulis == []


def test_catat_validasi(ss):
    with pytest.raises(eskalasi.EskalasiError, match="tim"):
        eskalasi.catat({**ISI, "tim": []}, ["333"], "Ani")
    with pytest.raises(eskalasi.EskalasiError, match="daftar pilihan"):
        eskalasi.catat({**ISI, "permasalahan": "Ngawur"}, ["333"], "Ani")
    with pytest.raises(eskalasi.EskalasiError, match="setelah hari ini"):
        eskalasi.catat({**ISI, "tgl_awal": "2026-12-01"}, ["333"], "Ani")


def test_ubah_selesai_isi_tanggal_dan_pengisi(ss):
    m = eskalasi.ubah("E-0001", {"jawaban": "Sudah diperbaiki tim aplikasi", "status": "Selesai"}, "Ani", False)
    assert m["status"] == "Selesai" and m["tgl_selesai"] == "2026-11-16" and m["pengisi"] == "Ani"
    m = eskalasi.ubah("E-0001", {"status": "Proses"}, "Ani", False)
    assert m["tgl_selesai"] == ""


def test_ubah_hak(ss):
    with pytest.raises(eskalasi.EskalasiError, match="milik Budi"):
        eskalasi.ubah("E-0007", {"jawaban": "x"}, "Ani", False)
    with pytest.raises(eskalasi.EskalasiError, match="PIC Eskalasi"):
        eskalasi.ubah("E-0001", {"kode_tema": "T01"}, "Ani", False)
    m = eskalasi.ubah("E-0007", {"kode_tema": "T02", "status_eskalasi": "Sudah Dieskalasi"}, "Nashwa", True)
    assert m["kode_tema"] == "T02" and m["status_eskalasi"] == "Sudah Dieskalasi"
    with pytest.raises(eskalasi.EskalasiError, match="daftar pilihan"):
        eskalasi.ubah("E-0007", {"kode_tema": "T99"}, "Nashwa", True)


def test_rentang_lompati_kolom_rumus():
    r = eskalasi.rentang(9, {0: "a", 1: "b", 3: "c"})
    assert [x["range"] for x in r] == ["'LK Eskalasi'!A9:B9", "'LK Eskalasi'!D9:D9"]
    assert r[0]["values"] == [["a", "b"]]


def test_tingkat_3_diawali_prioritas_tinggi(ss):
    eskalasi.catat({**ISI, "tingkat": "Tingkat 3 – Prioritas Tinggi"}, ["333"], "Ani")
    assert ss.data[2][9].startswith("PRIORITAS TINGGI: Sekolah belum")


def test_ubah_pakai_sidik_bukan_id(ss):
    m = eskalasi.daftar(["111"])[0]
    # ID rumus di sheet bergeser: baris lain kini ber-ID sama
    ss.data[1][0] = "E-0001"
    with pytest.raises(eskalasi.EskalasiError, match="dobel"):
        eskalasi.ubah("E-0001", {"jawaban": "x"}, "Ani", True)
    eskalasi.cache.clear()
    x = eskalasi.ubah("E-0001", {"jawaban": "Benar baris 5"}, "Ani", True, m["baris"], m["sidik"])
    assert x["baris"] == 5 and ss.data[0][27] == "Benar baris 5" and ss.data[1][27] == ""


def test_ubah_baris_bergeser_ketemu_lewat_sidik(ss):
    m = eskalasi.daftar(["222"])[0]
    ss.data.insert(0, baris("E-0100", "999", "Baris baru disisip di atas"))
    eskalasi.cache.clear()
    x = eskalasi.ubah(m["id"], {"jawaban": "ok"}, "Budi", False, m["baris"], m["sidik"])
    assert x["baris"] == m["baris"] + 1 and ss.data[2][27] == "ok"


def test_tanpa_agregasi_tanpa_tim(ss):
    h = eskalasi.catat({**ISI, "agregasi": "Tidak", "tim": ["Tim Aplikasi"]}, ["333"], "Ani")
    pos, _ = eskalasi.parse_judul(JUDUL)
    r = ss.data[2]
    assert r[pos["agregasi"]] == "Tidak" and not any(r[pos[f"tim:{t}"]] for t in TIM) and h[0]["id"] == "E-0008"
    with pytest.raises(eskalasi.EskalasiError, match="tim tujuan"):
        eskalasi.catat({**ISI, "tim": []}, ["333"], "Ani")
    m = eskalasi.daftar(["111"])[0]
    x = eskalasi.ubah(m["id"], {"agregasi": "Tidak"}, "Ani", False, m["baris"], m["sidik"])
    assert x["agregasi"] == "Tidak" and x["tim"] == []


def test_daftar_google_tidak_terbaca_jadi_502_bukan_500(monkeypatch):
    from fastapi import HTTPException

    from app.access import Access
    from app.routers import eskalasi as rute

    def gagal():
        raise RuntimeError("Belum masuk ke akun Google.")

    monkeypatch.setattr(eskalasi, "sheet_id", gagal)
    with pytest.raises(HTTPException) as e:
        rute.daftar(npsn="", semua=True, paksa=False, acc=Access("uji@contoh.id", "Uji", ("wa_blast",)))
    assert e.value.status_code == 502 and "Belum masuk" in e.value.detail
