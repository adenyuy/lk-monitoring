"""Logika pengenal pesan WhatsApp Web, memakai contoh struktur asli (Okt 2026)."""

from app.wa import actions
from app.wa.status import mask


def raw(labels=(), titles=(), icons=(), tail_out=False, tail_in=False, text=""):
    return {"id": "x", "text": text, "labels": list(labels), "titles": list(titles),
            "icons": list(icons), "tailOut": tail_out, "tailIn": tail_in}


def test_pesan_keluar_dibaca():
    r = raw(labels=["You:", " Read "], titles=["tail-out", "wds-ic-read"], icons=["tail-out"], tail_out=True)
    st = actions._status_of(r)
    assert st == "read" and actions._is_out(r, st)


def test_pesan_masuk():
    r = raw(labels=["Budi Santoso:"], titles=["tail-in"], icons=["tail-in"], tail_in=True)
    st = actions._status_of(r)
    assert st == "" and not actions._is_out(r, st)


def test_pesan_keluar_lanjutan_tanpa_ekor():
    r = raw(labels=[" Delivered "], titles=["wds-ic-msg-dblcheck"])
    st = actions._status_of(r)
    assert st == "delivered" and actions._is_out(r, st)


def test_status_menunggu_dan_terkirim():
    assert actions._status_of(raw(labels=["You:", " Pending "])) == "pending"
    assert actions._status_of(raw(labels=["Anda:", " Terkirim "])) == "sent"
    assert actions._status_of(raw(labels=["Anda:", " Dibaca "])) == "read"


def test_samarkan_nomor():
    assert mask("6281234567890") == "0812•••7890"
    assert mask("") == ""


def _row(out, text, status=""):
    return actions.Row("x", out, status, text)


def test_balasan_tetap_terhitung_walau_petugas_membalas_lagi():
    rows = [_row(True, "Pengumuman", "read"), _row(False, "Siap bu, segera saya ingatkan"),
            _row(True, "Terima kasih pak", "delivered")]
    info = actions.chat_info(rows)
    assert info.status == "dibalas" and info.balasan == ["Siap bu, segera saya ingatkan"]


def test_status_tanpa_balasan():
    assert actions.chat_info([_row(True, "Pengumuman", "read")]).status == "dibaca"
    assert actions.chat_info([_row(True, "Pengumuman", "delivered")]).status == "terkirim"
    assert actions.chat_info([_row(False, "Halo")]).status == "belum_ada"


def test_waktu_pesan():
    assert actions._waktu("[10:37, 26/10/2026] Budi: ") == "10.37, 26/10/2026"
    assert actions._waktu("") == ""


def test_rapikan_teks_daftar():
    teks = "Untuk sekolah berikut:\n\n\n\n1. SD A (39,6%)  \n2. SD B\n\n\n\nTerima kasih"
    assert actions.rapikan(teks) == "Untuk sekolah berikut:\n\n1. SD A (39,6%)\n2. SD B\n\nTerima kasih"


def test_rapikan_progres_mingguan_dari_whatsapp():
    # Bentuk yang terbaca dari WhatsApp Web: tiap butir jadi daftar sendiri ("1." semua) dan berjarak
    teks = ("berikut update progres:\n\n1. SD A (4,8%, belum submit)\nKendala progres fisik: ...\n\n"
            "Rencana tindak lanjut: ...\n\n1. SD B (62,4%, belum submit)\nKendala submit laporan 50%: ...\n\n"
            "Rencana unggah: ...\n\nMohon dibantu dijawab *per sekolah*. Terima kasih")
    assert actions.rapikan(teks) == (
        "berikut update progres:\n\n"
        "1. SD A (4,8%, belum submit)\n   Kendala progres fisik: ...\n   Rencana tindak lanjut: ...\n\n"
        "2. SD B (62,4%, belum submit)\n   Kendala submit laporan 50%: ...\n   Rencana unggah: ...\n\n"
        "Mohon dibantu dijawab *per sekolah*. Terima kasih")


def test_lampiran_ditandai():
    assert actions.teks_pesan("FOTO", "") == "[FOTO]"
    assert actions.teks_pesan("FOTO", "progres atap") == "[FOTO] progres atap"
    assert actions.teks_pesan("", "Siap pak") == "Siap pak"



def test_terakhir_masuk_artinya_perlu_dibalas():
    keluar, masuk = _row(True, "Broadcast", "read"), _row(False, "Siap pak")
    assert actions.chat_info([keluar, masuk]).terakhir_masuk
    assert not actions.chat_info([keluar, masuk, _row(True, "Terima kasih", "sent")]).terakhir_masuk
    assert not actions.chat_info([keluar]).terakhir_masuk
    assert not actions.chat_info([masuk, keluar]).terakhir_masuk  # pesan masuk sebelum broadcast bukan balasan


def baris_raw(id="x", pre="", text="", **kw):
    return {**raw(text=text, **kw), "id": id, "pre": pre}


def test_arah_dari_id_pesan():
    keluar = baris_raw(id="true_6281@c.us_3EB0AA", text="halo")  # tanpa ekor & ikon
    masuk = baris_raw(id="false_6281@c.us_ABC", text="baik", labels=[" Read "])
    rows = actions._baris([keluar, masuk])
    assert rows[0].out and not rows[1].out


def test_blast_tanpa_ikon_dikenali_dari_nama_pengirim():
    rows = actions._baris([
        baris_raw(pre="[10:00, 06/11/2026] Petugas: ", text="pesan awal", tail_out=True, labels=[" Read "]),
        baris_raw(pre="[10:01, 06/11/2026] Petugas: ", text="lanjutan panjang tanpa ikon"),
        baris_raw(pre="[11:00, 06/11/2026] Budi: ", text="oke", tail_in=True),
    ])
    assert [r.out for r in rows] == [True, True, False]
    assert actions.chat_info(rows).balasan == ["oke"]


def test_teks_blast_kita_tidak_dianggap_balasan():
    for teks in ("siang Bapak/Ibu Budi Santoso, izin menindaklanjuti progres pelaporan sekolah",
                 "Selamat siang Bapak/Ibu Sari Wulandari\n\nTerima kasih atas tanggapan Bapak/Ibu minggu lalu.",
                 "Berikut update progres Minggu ke-2 sekolah dampingan Bapak/Ibu yang laporan kemajuan"):
        rows = actions._baris([baris_raw(text="awal", tail_out=True, labels=[" Delivered "]),
                               baris_raw(text=teks, tail_in=True)])
        assert rows[1].out, teks
        assert actions.chat_info(rows).status != "dibalas"
    assert not actions.pesan_kita("Baik pak, terima kasih")
    assert not actions.pesan_kita("Selamat siang pak, berikut laporan progres sekolah saya")
