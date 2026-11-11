"""Status komponen, to-do per sekolah, dan keterangan otomatis di Kendala/Tindak Lanjut.

Prinsip "hijaukan dari kiri ke kanan", bertahap:
  1. Pendahuluan  : Lap. Pendahuluan belum dikirim -> hanya itu to-do-nya; komponen lain "Menunggu Lap. Pendahuluan".
  2. Berkala      : semua yang belum lengkap muncul sekaligus (Mingguan dan Bulanan boleh berbarengan).
                    Bulanan + BKU + BPP satu paket: diunggah bersamaan.
  3. Laporan 50%  : hanya bila sudah due. Progres < 50% -> to-do progres fisik, Lap. 50% "Menunggu progres 50%".
  4. Laporan 100% : hanya bila sudah due. Lap. 50% harus selesai dulu, lalu progres 100%.
Reviu adalah tugas fasil, unggah/kirim tugas sekolah. Petugas cukup mengisi Kendala/TL komponen yang jadi to-do;
sisanya diberi keterangan otomatis supaya jelas tidak perlu diisi.

Semua fungsi di sini murni (tanpa jaringan) supaya mudah dites.
"""

from dataclasses import dataclass, field
from typing import Any

from .lk_baru import KOMP, KOMPONEN, Sekolah

SELESAI, DUE, KOSONG, BERJALAN, TANPA_DATA = "✓ Selesai", "Belum due", "Belum ada laporan", "Berjalan", "Belum ada data"
AWALAN_MENUNGGU = "Menunggu "
MENUNGGU = {AWALAN_MENUNGGU + x for x in ("Lap. Pendahuluan", "progres 50%", "Lap. 50%", "progres 100%")}
OTOMATIS = {SELESAI, DUE, KOSONG, BERJALAN, TANPA_DATA} | MENUNGGU


def otomatis(teks: str) -> bool:
    """Keterangan yang ditulis aplikasi (boleh ditimpa lagi oleh aplikasi). Harus sama persis:
    pilihan Kendala petugas seperti "Menunggu pencairan" bukan keterangan otomatis."""
    return (teks or "").strip() in OTOMATIS


# ---------- status satu komponen ----------

@dataclass(frozen=True)
class Status:
    kode: str
    status: str      # selesai | belum | due | kosong | tanpa_data
    tampil: str      # teks singkat untuk tampilan, mis. '3/5', '42%', 'Revisi'
    rasio: tuple[float, float] | None = None
    persen: float | None = None  # progres 0..100


def _angka(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None


def status(kode: str, v: Any) -> Status:
    t = str(v if v is not None else "").strip()
    if t == "":
        return Status(kode, "tanpa_data", "–")
    if t.lower() == "belum due":
        return Status(kode, "due", "Belum due")
    if t == "-":
        return Status(kode, "kosong", "Belum ada laporan")
    if kode == "progres":
        p = _angka(v)
        if p is None:
            return Status(kode, "tanpa_data", t)
        # angka dari sheet berupa pecahan (kolom berformat %): 1.0033 = 100,33%, bukan 1%
        p = p * 100 if p <= 2.0 and isinstance(v, (int, float)) else p
        return Status(kode, "selesai" if p >= 100 else "belum", f"{p:.0f}%".replace(".", ","), persen=p)
    if "/" in t:
        try:
            a, b = (float(x) for x in t.split("/", 1))
        except ValueError:
            return Status(kode, "belum", t)
        if b <= 0:
            return Status(kode, "kosong", "Belum ada laporan")
        return Status(kode, "selesai" if a >= b else "belum", f"{a:g}/{b:g}", rasio=(a, b))
    # "Disetujui Fasil" (Reviu Lap. 100%) = sudah direviu dan sesuai
    return Status(kode, "selesai" if t.casefold() in ("sudah", "disetujui fasil") else "belum", t)


def semua_status(s: Sekolah) -> dict[str, Status]:
    return {k.kode: status(k.kode, s.nilai.get(k.kode, "")) for k in KOMPONEN}


# ---------- to-do ----------

@dataclass
class Todo:
    kode: str                      # kode to-do (sama dengan komponen, atau 'paket_bulanan')
    judul: str                     # kalimat singkat apa yang harus dilakukan
    pelaku: str                    # sekolah | fasil
    komponen: list[str]            # komponen yang Kendala/TL-nya diisi untuk to-do ini
    detail: str = ""               # angka pendukung, mis. '3/5 terunggah'
    tunggu: float | None = None    # hari menunggu reviu


@dataclass
class Rencana:
    status: dict[str, Status]
    todo: list[Todo] = field(default_factory=list)
    menunggu: dict[str, str] = field(default_factory=dict)  # komponen -> 'Menunggu ...'
    tahap: str = "selesai"         # pendahuluan | berkala | l50 | l100 | selesai

    @property
    def fokus(self) -> Todo | None:
        return self.todo[0] if self.todo else None

    def komponen_todo(self) -> set[str]:
        return {k for t in self.todo for k in t.komponen}

    def keterangan(self, kode: str) -> str:
        """Keterangan otomatis untuk Kendala/TL komponen ini, atau '' bila harus diisi petugas."""
        if kode in self.komponen_todo():
            return ""
        if kode in self.menunggu:
            return self.menunggu[kode]
        st = self.status[kode].status
        return {"selesai": SELESAI, "due": DUE, "kosong": KOSONG, "tanpa_data": TANPA_DATA}.get(st, BERJALAN)


def _rasio_teks(st: Status, akhiran: str) -> str:
    if st.rasio:
        a, b = st.rasio
        return f"{a:g}/{b:g} {akhiran}"
    return st.tampil


def rencana(s: Sekolah) -> Rencana:
    st = semua_status(s)
    r = Rencana(st)
    belum = lambda k: st[k].status == "belum"  # noqa: E731

    def reviu(kode: str, apa: str) -> None:
        if belum(kode):
            r.todo.append(Todo(kode, f"Reviu {apa}", "fasil", [kode],
                               detail=_rasio_teks(st[kode], "direviu") if st[kode].rasio else st[kode].tampil,
                               tunggu=s.tunggu.get(kode)))

    # 1. Pendahuluan: gerbang semua komponen lain
    if belum("lp"):
        r.todo.append(Todo("lp", "Kirim Laporan Pendahuluan", "sekolah", ["lp"], detail=st["lp"].tampil))
        r.tahap = "pendahuluan"
        for k in KOMPONEN:
            if k.kode != "lp" and st[k.kode].status in ("belum", "tanpa_data"):
                r.menunggu[k.kode] = AWALAN_MENUNGGU + "Lap. Pendahuluan"
        return r
    reviu("lp_rev", "Laporan Pendahuluan")
    if r.todo:
        r.tahap = "pendahuluan"

    # 2. Berkala
    if belum("mg"):
        r.todo.append(Todo("mg", "Lengkapi Laporan Mingguan", "sekolah", ["mg"],
                           detail=_rasio_teks(st["mg"], "terunggah")))
    reviu("mg_rev", "Laporan Mingguan")
    paket = [k for k in ("bl", "bku", "bpp") if belum(k)]
    if paket:
        nama = " + ".join(KOMP[k].label.replace("Lap. ", "") for k in paket)
        r.todo.append(Todo("paket_bulanan", f"Unggah {nama}", "sekolah", paket,
                           detail=_rasio_teks(st["bl"], "terunggah") if "bl" in paket else "BKU dan BPP diunggah bersama Lap. Bulanan"))
    reviu("bl_rev", "Laporan Bulanan")
    if r.todo and r.tahap == "selesai":
        r.tahap = "berkala"

    persen = st["progres"].persen

    # 3. Laporan 50%
    if belum("l50"):
        if persen is not None and persen < 50:
            r.todo.append(Todo("progres", "Kejar progres fisik ke 50%", "sekolah", ["progres"],
                               detail=f"Progres {st['progres'].tampil}, Lap. 50% butuh ≥ 50%"))
            r.menunggu["l50"] = AWALAN_MENUNGGU + "progres 50%"
        else:
            r.todo.append(Todo("l50", "Unggah Laporan 50%", "sekolah", ["l50"], detail=st["l50"].tampil))
        if r.tahap == "selesai":
            r.tahap = "l50"
    reviu("l50_rev", "Laporan 50%")

    # 4. Laporan 100%
    if belum("l100"):
        if st["l50"].status != "selesai":
            r.menunggu["l100"] = AWALAN_MENUNGGU + "Lap. 50%"
        elif persen is not None and persen < 100:
            if "progres" not in r.komponen_todo():
                r.todo.append(Todo("progres", "Kejar progres fisik ke 100%", "sekolah", ["progres"],
                                   detail=f"Progres {st['progres'].tampil}, Lap. 100% butuh 100%"))
            r.menunggu["l100"] = AWALAN_MENUNGGU + "progres 100%"
        else:
            r.todo.append(Todo("l100", "Unggah Laporan 100%", "sekolah", ["l100"], detail=st["l100"].tampil))
        if r.tahap == "selesai":
            r.tahap = "l100"
    reviu("l100_rev", "Laporan 100%")
    if r.todo and r.tahap == "selesai":
        r.tahap = "l100" if any(t.kode.startswith("l100") for t in r.todo) else "l50"
    return r


def lengkap(s: Sekolah, r: Rencana, blok: int) -> bool:
    """Isian sesi `blok` lengkap: semua komponen to-do punya Kendala dan Tindak Lanjut buatan petugas."""
    isi = s.isian.get(blok, {})
    for k in r.komponen_todo():
        kendala, tl = isi.get(k, ("", ""))
        if not kendala or otomatis(kendala) or not tl or otomatis(tl):
            return False
    return True


def keterangan_baru(s: Sekolah, r: Rencana) -> list[tuple[int, str, str, str]]:
    """Sel Kendala/TL yang perlu diperbarui: [(blok, kode, kendala_baru, tl_baru)].
    Hanya sel kosong atau berisi keterangan otomatis yang diubah; isian petugas tidak ditimpa."""
    out = []
    for blok, isi in s.isian.items():
        for k in KOMPONEN:
            ket = r.keterangan(k.kode)
            kendala, tl = isi.get(k.kode, ("", ""))
            baru_k = ket if (not kendala or otomatis(kendala)) else kendala
            baru_t = ket if (not tl or otomatis(tl)) else tl
            if (baru_k, baru_t) != (kendala, tl):
                out.append((blok, k.kode, baru_k, baru_t))
    return out


def ringkas(s: Sekolah, r: Rencana, blok: int) -> dict[str, Any]:
    """Bentuk JSON untuk tampilan."""
    isi = s.isian.get(blok, {})
    return {
        "npsn": s.npsn, "nama": s.nama, "angkatan": s.angkatan, "kab": s.kab,
        "tahap": r.tahap,
        "komponen": [{"kode": k.kode, "label": k.label, "tahap": k.tahap, "pelaku": k.pelaku,
                      "status": r.status[k.kode].status, "tampil": r.status[k.kode].tampil,
                      "tunggu": s.tunggu.get(k.kode), "menunggu": r.menunggu.get(k.kode, "")} for k in KOMPONEN],
        "todo": [{"kode": t.kode, "judul": t.judul, "pelaku": t.pelaku, "komponen": t.komponen, "detail": t.detail,
                  "tunggu": t.tunggu,
                  "isian": {k: {"kendala": "" if otomatis(isi.get(k, ("", ""))[0]) else isi.get(k, ("", ""))[0],
                                "tl": "" if otomatis(isi.get(k, ("", ""))[1]) else isi.get(k, ("", ""))[1]}
                            for k in t.komponen}} for t in r.todo],
        "lengkap": lengkap(s, r, blok),
        "selesai": sum(1 for x in r.status.values() if x.status == "selesai"),
        "relevan": sum(1 for x in r.status.values() if x.status in ("selesai", "belum")),
    }
