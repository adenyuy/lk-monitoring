from app import send_queue
from app.sheets import BroadcastRow, message_hash


def row(baris, nama, nomor, pesan="Halo"):
    return BroadcastRow(baris, "Sari Petugas", nama, nomor, nomor, pesan, message_hash(pesan) if pesan else "")


def send(nomor, pesan, status, ket="", waktu="2026-10-26T10:00:00"):
    return {"nomor": nomor, "hash_pesan": message_hash(pesan), "status": status, "keterangan": ket, "waktu": waktu}


ROWS = [
    row(2, "A", "6281100000001"),
    row(3, "B", "6281100000002"),
    row(4, "C", ""),  # nomor tidak valid
    row(5, "D", "6281100000004", pesan=""),  # pesan kosong
    row(6, "A lagi", "6281100000001"),  # dobel dengan baris 2
    row(7, "E", "6281100000005"),
    row(8, "F", "6281100000006"),
]


def test_status_tiap_baris():
    sends = [
        send("6281100000002", "Halo", "terkirim"),
        send("6281100000005", "Halo", "gagal", "Nomor tidak terdaftar di WhatsApp (nomor_tidak_terdaftar)"),
        send("6281100000006", "Halo", "gagal", "Chat tidak terbuka dalam 45 detik"),
    ]
    items = {i.nama_fasil: i for i in send_queue.build(ROWS, sends)}
    assert items["A"].status == "menunggu"
    assert items["B"].status == "terkirim"
    assert items["C"].status == "dilewati" and "Nomor tidak valid" in items["C"].keterangan
    assert items["D"].status == "dilewati" and items["D"].keterangan == "Pesan kosong"
    assert items["A lagi"].status == "dilewati" and "baris 2" in items["A lagi"].keterangan
    assert items["E"].status == "gagal" and not items["E"].bisa_dikirim  # gagal permanen
    assert items["F"].status == "gagal" and items["F"].bisa_dikirim  # dicoba lagi


def test_urutan_eligible_belum_pernah_dulu_lalu_ulang():
    sends = [send("6281100000001", "Halo", "gagal", "timeout")]
    names = [i.nama_fasil for i in send_queue.eligible(send_queue.build(ROWS, sends))]
    assert names == ["B", "E", "F", "A"]


def test_pesan_berubah_masuk_antrean_lagi():
    sends = [send("6281100000002", "Halo versi lama", "terkirim")]
    items = {i.nama_fasil: i for i in send_queue.build(ROWS, sends)}
    assert items["B"].status == "menunggu"
