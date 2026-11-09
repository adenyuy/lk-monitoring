"""Aksi di WhatsApp Web: buka chat, kirim, cek terkirim, baca chat.

Semua fungsi menerima `Browser` dan harus dipanggil lewat `worker.call(...)`.
"""

import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote

from playwright.sync_api import Page

from . import selectors as S
from .browser import Browser
from .status import first_visible, state


class NotLoggedIn(Exception):
    """WhatsApp Web logout / meminta scan QR. Pengiriman harus berhenti total."""


@dataclass
class OpenResult:
    ok: bool
    alasan: str = ""  # diisi bila ok=False: 'nomor_tidak_terdaftar' | 'timeout' | 'teks_tidak_terisi'


@dataclass
class SendResult:
    status: str  # 'terkirim' | 'gagal'
    keterangan: str = ""
    centang: str = ""  # sent | delivered | read (ikon pesan terakhir saat dicek)


@dataclass
class ChatInfo:
    status: str  # 'belum_ada' | 'terkirim' | 'dibaca' | 'dibalas'
    pesan_keluar_terakhir: str = ""
    balasan: list[str] = field(default_factory=list)
    centang: str = ""  # ikon pesan keluar PERTAMA (broadcast): sent | delivered | read
    terakhir_masuk: bool = False  # pesan terakhir di chat berasal dari fasil (belum kita balas)


def _norm(s: str) -> str:
    return " ".join(str(s).split()).casefold()


def _popup_text(page: Page) -> str:
    sel = first_visible(page, S.POPUP)
    if not sel:
        return ""
    try:
        return _norm(page.inner_text(sel))
    except Exception:
        return ""


def _compose(page: Page):
    sel = first_visible(page, S.COMPOSE)
    return page.query_selector(sel) if sel else None


def open_chat(b: Browser, nomor: str, teks: str = "", timeout: float = 45) -> OpenResult:
    """Buka chat ke `nomor` (format 62…) dengan `teks` terisi di kotak pesan (belum dikirim)."""
    page = b.page
    url = f"{S.WA_URL}send?phone={nomor}"
    if teks:
        url += f"&text={quote(teks)}"
    page.goto(url, wait_until="domcontentloaded")

    expect = _norm(teks)[:40]
    end = time.time() + timeout
    while time.time() < end:
        page.wait_for_timeout(700)
        if state(page) == "qr":
            raise NotLoggedIn("WhatsApp Web meminta scan QR ulang.")
        popup = _popup_text(page)
        if popup and any(t in popup for t in S.INVALID_NUMBER_TEXT):
            return OpenResult(False, "nomor_tidak_terdaftar")
        box = _compose(page)
        if box is not None:
            if not expect:
                return OpenResult(True)
            # Teks dari URL kadang baru muncul sesaat setelah kotak pesan siap.
            if expect in _norm(box.inner_text()):
                return OpenResult(True)
    box = _compose(page)
    if box is not None and expect:
        return OpenResult(False, "teks_tidak_terisi")
    return OpenResult(False, "timeout")


def clear_draft(b: Browser) -> None:
    """Hapus teks di kotak pesan (dipakai setelah mode coba agar tidak jadi draft)."""
    box = _compose(b.page)
    if box is None:
        return
    box.click()
    b.page.keyboard.press("Control+A")
    b.page.keyboard.press("Delete")


_ROWS_JS = """
([rowSels, textSels, tailOut, tailIn, quoteSel]) => {
  // WhatsApp menampilkan baris "1. ..." sebagai daftar bernomor (<ol>); nomornya dari CSS sehingga
  // hilang di innerText. Salin elemen ke luar layar, tulis nomornya sebagai teks, lalu baca.
  const teks = (el) => {
    if (!el.querySelector('ol, ul')) return el.innerText;
    const c = el.cloneNode(true);
    let lanjut = 1;  // tiap butir bisa berupa <ol> sendiri: lanjutkan nomor bila tidak ada atribut start
    c.querySelectorAll('ol').forEach(ol => {
      const st = ol.getAttribute('start');
      let n = st ? Number(st) : lanjut;
      [...ol.children].forEach(li => {
        const v = li.getAttribute('value');
        if (v) n = Number(v);
        li.prepend(document.createTextNode(n + '. '));
        n += 1;
      });
      lanjut = n;
    });
    c.querySelectorAll('ul > li').forEach(li => li.prepend(document.createTextNode('• ')));
    const wadah = document.createElement('div');
    wadah.style.cssText = 'position:fixed;left:-99999px;top:0;width:600px;white-space:pre-wrap';
    wadah.appendChild(c);
    document.body.appendChild(wadah);
    const hasil = c.innerText;
    wadah.remove();
    return hasil;
  };
  let rows = [];
  for (const s of rowSels) { rows = [...document.querySelectorAll(s)]; if (rows.length) break; }
  return rows.map(r => {
    // Balasan yang mengutip pesan lain berisi dua teks: kutipan (di atas) lalu isi balasan.
    // Ambil isi balasan = teks terakhir yang tidak berada di dalam kotak kutipan.
    let text = '', kutipan = '';
    for (const s of textSels) {
      const semua = [...r.querySelectorAll(s)];
      if (!semua.length) continue;
      // Teks berformat (tebal, daftar) berisi potongan bertumpuk dengan selektor yang sama: pakai wadah terluar saja
      const atas = semua.filter(el => !semua.some(o => o !== el && o.contains(el)));
      const luar = atas.filter(el => !el.closest(quoteSel));
      const dalam = atas.filter(el => el.closest(quoteSel));
      text = teks(luar.length ? luar[luar.length - 1] : atas[0]);
      if (!text.trim()) text = teks(atas[0]);
      if (dalam.length) kutipan = dalam[0].innerText;
      break;
    }
    if (!kutipan) { const q = r.querySelector(quoteSel); if (q) kutipan = q.innerText; }
    const labels = [...r.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label') || '');
    const titles = [...r.querySelectorAll('svg title')].map(t => t.textContent || '');
    const icons = [...r.querySelectorAll('[data-icon]')].map(e => e.getAttribute('data-icon') || '');
    const pre = r.querySelector('[data-pre-plain-text]');
    // Lampiran (di luar kotak kutipan): foto, video, pesan suara, dokumen
    const luarKutipan = (el) => !el.closest(quoteSel);
    const ikon = icons.join(' ').toLowerCase();
    const foto = [...r.querySelectorAll('img')].some(im => luarKutipan(im) && !im.closest('a[href^="http"]')
      && !im.classList.contains('emoji') && im.getBoundingClientRect().width >= 100
      && im.getBoundingClientRect().height >= 70);
    let media = '';
    if (/video|media-play|media-gif/.test(ikon)) media = 'VIDEO';
    else if (/audio|ptt|voice/.test(ikon) || r.querySelector('audio')) media = 'PESAN SUARA';
    else if (/document|doc-/.test(ikon)) media = 'DOKUMEN';
    else if (foto) media = 'FOTO';
    return {
      media,
      // data-id "true_<jid>_<id>" = pesan kita, "false_..." = pesan masuk (penanda arah paling andal)
      id: r.getAttribute('data-id') || (r.querySelector('[data-id]') || r.closest('[data-id]') || r).getAttribute('data-id')
        || (r.getAttribute('data-testid') || '').replace(/^conv-msg-/, '') || '',
      pre: pre ? pre.getAttribute('data-pre-plain-text') || '' : '',
      text: text || '',
      kutipan: kutipan || '',
      labels, titles, icons,
      tailOut: !!r.querySelector(tailOut),
      tailIn: !!r.querySelector(tailIn),
    };
  });
}
"""


@dataclass
class Row:
    id: str
    out: bool
    status: str  # pending | sent | delivered | read | '' (pesan masuk)
    text: str
    waktu: str = ""  # "10.37, 26/10/2026" dari atribut data-pre-plain-text, bila ada
    kutipan: str = ""  # teks pesan yang dikutip (bila pesan ini membalas pesan lain)


_NOMOR = re.compile(r"^(\d{1,3})\.\s+\S")
_LABEL = re.compile(r"^[^:\n]{2,40}:(\s|$)")  # "Kendala progres fisik: ..."


def rapikan(teks: str) -> str:
    """Rapikan teks yang dibaca dari WhatsApp Web:
    - buang spasi di ujung baris dan baris kosong berlebih (daftar WhatsApp menambah jarak);
    - daftar yang semua nomornya terbaca "1." dinomori ulang 1, 2, 3, ...;
    - di dalam satu butir bernomor, baris "Label: isi" tidak dipisah baris kosong dan diberi inden,
      dan antar-butir yang berbaris banyak dipisah satu baris kosong."""
    baris = [b.rstrip() for b in teks.replace("\r", "").split("\n")]
    nomor = [i for i, b in enumerate(baris) if _NOMOR.match(b.strip())]
    if len(nomor) > 1 and all(_NOMOR.match(baris[i].strip()).group(1) == "1" for i in nomor):
        for n, i in enumerate(nomor, 1):
            baris[i] = f"{n}." + baris[i].strip()[2:]

    out: list[str] = []
    dalam_butir = False  # sedang di dalam butir bernomor
    butir_panjang = False  # butir saat ini punya baris lanjutan
    for b in baris:
        s = b.strip()
        if _NOMOR.match(s):
            if dalam_butir and butir_panjang:
                while out and out[-1] == "":
                    out.pop()
                out.append("")
            dalam_butir, butir_panjang = True, False
            out.append(s)
        elif dalam_butir and s and _LABEL.match(s):
            while out and out[-1] == "":
                out.pop()
            out.append("   " + s)
            butir_panjang = True
        else:
            if s and (not out or out[-1] == ""):
                dalam_butir = False  # teks biasa setelah baris kosong: daftar sudah selesai
            out.append(b)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _waktu(pre: str) -> str:
    """'[10:37, 26/10/2026] Nama: ' -> '10.37, 26/10/2026'."""
    if not pre.startswith("[") or "]" not in pre:
        return ""
    return pre[1 : pre.index("]")].replace(":", ".").strip()


def _status_of(raw: dict) -> str:
    hay = " ".join(raw["labels"] + raw["titles"] + raw["icons"]).casefold()
    for name, keys in S.STATUS_KEYWORDS:
        if any(k in hay for k in keys):
            return name
    return ""


def _arah_id(pid: str) -> bool | None:
    """Arah pesan dari ID WhatsApp Web: 'true_…' = pesan kita, 'false_…' = pesan masuk, selain itu tidak tahu."""
    if pid.startswith("true_"):
        return True
    if pid.startswith("false_"):
        return False
    return None


def _pengirim(pre: str) -> str:
    """'[10:37, 26/10/2026] Nama: ' -> 'nama'."""
    if "]" not in (pre or ""):
        return ""
    return _norm(pre[pre.index("]") + 1:].strip().rstrip(":"))


def _is_out(raw: dict, status: str) -> bool:
    arah = _arah_id(raw.get("id", ""))
    if arah is not None:
        return arah
    if raw["tailOut"]:
        return True
    if raw["tailIn"]:
        return False
    labels = [_norm(x) for x in raw["labels"]]
    if any(lbl in S.OUT_SENDER_LABELS for lbl in labels):
        return True
    # Pesan lanjutan tanpa "ekor": pesan keluar selalu punya ikon status.
    return bool(status)


def rows(page: Page) -> list[Row]:
    raw = page.evaluate(_ROWS_JS, [list(S.MESSAGE_ROW), list(S.MESSAGE_TEXT), S.TAIL_OUT, S.TAIL_IN, S.QUOTE])
    return _baris(raw)


def _pasti(r: dict) -> bool:
    """Arah pesan ini diketahui pasti (ID, ekor, atau label "You:"), bukan tebakan dari ikon status."""
    labels = [_norm(x) for x in r["labels"]]
    return (_arah_id(r.get("id", "")) is not None or r["tailOut"] or r["tailIn"]
            or any(lbl in S.OUT_SENDER_LABELS for lbl in labels))


# Pesan kita ke fasil (blast, progres mingguan, survei, undangan WAG) menyapa "Bapak/Ibu …"; fasil tidak menyapa
# dirinya sendiri begitu. Bisa terpotong di depan ("siang Bapak/Ibu …") bila "Selamat" berformat terpisah.
_PESAN_KITA = re.compile(r"^\W*(selamat\s+)?(pagi|siang|sore|malam)\s+bapak\s*/\s*ibu\b"
                         r"|sekolah\s+dampingan\s+bapak\s*/\s*ibu|tanggapan\s+bapak\s*/\s*ibu"
                         r"|kerja\s*sama\s+bapak\s*/\s*ibu|bapak\s*/\s*ibu[^\n]{0,80}izin\s+menindaklanjuti", re.I)


def pesan_kita(teks: str) -> bool:
    return bool(_PESAN_KITA.search(teks or ""))


def _baris(raw: list[dict]) -> list[Row]:
    status = [_status_of(r) for r in raw]
    arah = [_is_out(r, st) for r, st in zip(raw, status)]
    # Pesan tanpa ekor yang ikon centangnya tidak terbaca (mis. blast panjang) bisa tertebak "masuk".
    # Pembanding: nama pengirim di label "[jam, tanggal] Nama:" pesan yang arahnya sudah pasti.
    kita = {_pengirim(r.get("pre", "")) for r, o in zip(raw, arah) if o and _pasti(r)} - {""}
    fasil = {_pengirim(r.get("pre", "")) for r, o in zip(raw, arah) if not o and _pasti(r)} - {""}
    out = []
    for r, st, o in zip(raw, status, arah):
        if not _pasti(r):
            p = _pengirim(r.get("pre", ""))
            if p in kita and p not in fasil:
                o = True
            elif p in fasil and p not in kita:
                o = False
        if not o and _arah_id(r.get("id", "")) is None and pesan_kita(r["text"]):
            o = True
        out.append(Row(r["id"], o, st if o else "", teks_pesan(r.get("media", ""), r["text"]),
                       _waktu(r.get("pre", "")), rapikan(r.get("kutipan", ""))))
    return out


def teks_pesan(media: str, teks: str) -> str:
    """Teks pesan; lampiran ditandai, mis. "[FOTO]" atau "[FOTO] keterangan foto"."""
    teks = rapikan(teks)
    if not media:
        return teks
    return f"[{media}]" + (("\n" if "\n" in teks else " ") + teks if teks else "")


# Pesan panjang dipotong WhatsApp dengan tombol "Baca selengkapnya": buka dulu supaya terbaca utuh
_BACA_SELENGKAPNYA_JS = """
() => {
  const kata = ['baca selengkapnya', 'read more', 'selengkapnya'];
  const el = [...document.querySelectorAll('#main [role="button"], #main .read-more-button')]
    .filter(e => kata.includes((e.innerText || '').trim().toLowerCase()));
  el.forEach(e => e.click());
  return el.length;
}
"""


def buka_pesan_panjang(page: Page) -> None:
    for _ in range(3):  # pesan sangat panjang bisa perlu dibuka beberapa kali
        try:
            if not page.evaluate(_BACA_SELENGKAPNYA_JS):
                return
        except Exception:
            return
        page.wait_for_timeout(300)


def send(b: Browser, timeout: float = 30) -> SendResult:
    """Tekan kirim pada chat yang sedang terbuka, lalu pastikan pesan tidak lagi berikon jam."""
    page = b.page
    before_ids = {r.id for r in rows(page)}
    btn_sel = first_visible(page, S.SEND_BUTTON)
    if btn_sel:
        page.click(btn_sel)
    else:
        box = _compose(page)
        if box is None:
            return SendResult("gagal", "Kotak pesan tidak ditemukan.")
        box.press("Enter")

    end = time.time() + timeout
    new_out: list[Row] = []
    while time.time() < end:
        page.wait_for_timeout(700)
        new_out = [r for r in rows(page) if r.out and r.id not in before_ids]
        if new_out and new_out[-1].status in ("sent", "delivered", "read"):
            # tunggu sebentar: centang dua biasanya muncul 1-3 detik setelah centang satu
            for _ in range(5):
                if new_out[-1].status != "sent":
                    break
                page.wait_for_timeout(700)
                new_out = [r for r in rows(page) if r.out and r.id not in before_ids] or new_out
            return SendResult("terkirim", centang=new_out[-1].status)
    if new_out:
        return SendResult("gagal", "Pesan masih menunggu (ikon jam) setelah 30 detik.")
    return SendResult("gagal", "Pesan tidak muncul di chat setelah menekan kirim.")


def chat_info(all_rows: list[Row]) -> ChatInfo:
    """Status chat dari baris yang terlihat. Balasan = pesan masuk setelah pesan keluar PERTAMA,
    supaya balasan fasil tetap terhitung walau petugas sudah membalas lagi sesudahnya."""
    first_out = next((i for i, r in enumerate(all_rows) if r.out), -1)
    if first_out < 0:
        return ChatInfo("belum_ada")
    last_out = max(i for i, r in enumerate(all_rows) if r.out)
    balasan = [r.text for r in all_rows[first_out + 1 :] if not r.out and r.text]
    if balasan:
        status = "dibalas"
    else:
        status = "dibaca" if all_rows[last_out].status == "read" else "terkirim"
    berisi = [r for r in all_rows if r.text]
    terakhir_masuk = bool(balasan) and bool(berisi) and not berisi[-1].out
    return ChatInfo(status, all_rows[last_out].text, balasan, all_rows[first_out].status, terakhir_masuk)


def read_thread(b: Browser, nomor: str) -> tuple[ChatInfo, list[Row]]:
    """Buka chat `nomor` lalu kembalikan status + semua pesan yang terlihat."""
    res = open_chat(b, nomor)
    if not res.ok:
        return ChatInfo("belum_ada"), []
    b.page.wait_for_timeout(1500)  # beri waktu riwayat chat dimuat
    buka_pesan_panjang(b.page)
    all_rows = rows(b.page)
    return chat_info(all_rows), all_rows


def read_chat(b: Browser, nomor: str) -> ChatInfo:
    return read_thread(b, nomor)[0]


def reply(b: Browser, nomor: str, teks: str) -> SendResult:
    """Kirim satu pesan balasan ke `nomor`."""
    res = open_chat(b, nomor, teks)
    if not res.ok:
        alasan = {"nomor_tidak_terdaftar": "Nomor tidak terdaftar di WhatsApp.",
                  "teks_tidak_terisi": "Teks balasan tidak masuk ke kotak pesan."}.get(res.alasan, "Chat tidak terbuka.")
        return SendResult("gagal", alasan)
    return send(b)
