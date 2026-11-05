// Template pesan WhatsApp (fasil, koordinator, kepala sekolah) yang isinya mengikuti to-do tiap sekolah,
// dan pembaca balasan fasil yang memakai format "Kendala: … / Tindak lanjut: …".

import type { JenisPenerima, Penerima, TodoRingkas } from "./lk";

export type Template = { kode: string; judul: string; ket: string; teks: string; bawaan: boolean };

export const SALAM = "{salam}";

export function salamSekarang(d = new Date()) {
  const h = d.getHours();
  return h < 11 ? "Selamat pagi" : h < 15 ? "Selamat siang" : h < 18 ? "Selamat sore" : "Selamat malam";
}

const TERIMA_KASIH = "Terima kasih atas perhatian dan kerja samanya 🙏";

/** Variabel yang bisa dipakai di pesan, per jenis penerima. */
export const VARIABEL: Record<JenisPenerima, { kode: string; arti: string }[]> = {
  fasil: [
    { kode: "{salam}", arti: "Selamat pagi/siang/sore/malam (otomatis saat dikirim)" },
    { kode: "{nama}", arti: "Nama fasil" },
    { kode: "{jumlah_sekolah}", arti: "Jumlah sekolah yang masih punya to-do" },
    { kode: "{daftar_tanya}", arti: "Daftar sekolah + to-do + baris Kendala/Tindak lanjut" },
    { kode: "{daftar_todo}", arti: "Daftar sekolah + to-do (tanpa isian)" },
    { kode: "{daftar_reviu}", arti: "Laporan yang menunggu reviu fasil" },
    { kode: "{petugas}", arti: "Nama Anda" },
  ],
  koor: [
    { kode: "{salam}", arti: "Salam sesuai jam" },
    { kode: "{nama}", arti: "Nama koordinator" },
    { kode: "{daftar_sulit}", arti: "Fasil yang sulit dihubungi" },
    { kode: "{daftar_fasil}", arti: "Rekap to-do per fasil binaan" },
    { kode: "{petugas}", arti: "Nama Anda" },
  ],
  sekolah: [
    { kode: "{salam}", arti: "Salam sesuai jam" },
    { kode: "{nama}", arti: "Nama kepala sekolah" },
    { kode: "{sekolah}", arti: "Nama sekolah" },
    { kode: "{daftar_todo}", arti: "Laporan yang perlu dilengkapi sekolah" },
    { kode: "{petugas}", arti: "Nama Anda" },
  ],
};

function poin(t: TodoRingkas, fasilSebagaiKamu: boolean) {
  const det = t.detail && !/^(Belum|Sudah)$/.test(t.detail) ? ` (${t.detail})` : "";
  const oleh = t.pelaku === "fasil" && fasilSebagaiKamu ? " — oleh Bapak/Ibu" : "";
  return `• ${t.judul}${det}${oleh}`;
}

/** Sekolah dengan to-do, diurutkan nama (urutan ini juga dipakai saat membaca balasan). */
export function sekolahTodo(p: Pick<Penerima, "sekolah">) {
  return (p.sekolah ?? []).filter((x) => x.todo.length).slice().sort((a, b) => a.nama.localeCompare(b.nama));
}

function daftarTanya(p: Penerima) {
  return sekolahTodo(p).map((x, i) =>
    `${i + 1}. *${x.nama}*\n${x.todo.map((t) => `   ${poin(t, true)}`).join("\n")}\n   Kendala: ...\n   Tindak lanjut: ...`,
  ).join("\n\n");
}

function daftarTodo(p: Penerima) {
  return sekolahTodo(p).map((x, i) =>
    `${i + 1}. *${x.nama}*\n${x.todo.map((t) => `   ${poin(t, true)}`).join("\n")}`).join("\n\n");
}

function daftarReviu(p: Penerima) {
  const xs = sekolahTodo(p)
    .map((x) => ({ nama: x.nama, todo: x.todo.filter((t) => t.pelaku === "fasil") }))
    .filter((x) => x.todo.length);
  return xs.map((x, i) => `${i + 1}. *${x.nama}*\n${x.todo.map((t) => `   ${poin(t, false)}`).join("\n")}`)
    .join("\n\n");
}

function daftarSulit(p: Penerima) {
  return (p.fasil ?? []).filter((f) => f.sulit)
    .map((f, i) => `${i + 1}. ${f.nama} (${f.sekolah} sekolah dampingan)`).join("\n");
}

function daftarFasil(p: Penerima) {
  return (p.fasil ?? []).filter((f) => f.perlu)
    .map((f, i) => {
      const rev = f.todo_fasil ? `, ${f.todo_fasil} laporan menunggu reviu fasil` : "";
      return `${i + 1}. ${f.nama}: ${f.perlu} dari ${f.sekolah} sekolah masih perlu melengkapi laporan${rev}`;
    }).join("\n");
}

/** Isi variabel untuk satu penerima. `{salam}` dibiarkan bila `salamNanti` (diisi server saat dikirim). */
export function isi(teks: string, p: Penerima, petugas: string, salamNanti = true) {
  const sTodo = sekolahTodo(p);
  const peta: Record<string, () => string> = {
    "{nama}": () => (p.kepsek || p.nama).trim(),
    "{petugas}": () => petugas,
    "{jumlah_sekolah}": () => String(sTodo.length),
    "{daftar_tanya}": () => daftarTanya(p),
    "{daftar_todo}": () => (p.todo ? p.todo.map((t) => poin(t, false)).join("\n") : daftarTodo(p)),
    "{daftar_reviu}": () => daftarReviu(p),
    "{daftar_sulit}": () => daftarSulit(p),
    "{daftar_fasil}": () => daftarFasil(p),
    "{sekolah}": () => p.nama,
  };
  let out = teks;
  for (const [k, f] of Object.entries(peta)) if (out.includes(k)) out = out.split(k).join(f());
  if (!salamNanti) out = out.split(SALAM).join(salamSekarang());
  return out;
}

/** Variabel yang hasilnya kosong untuk penerima ini (mis. tidak ada reviu) -> pesan sebaiknya tidak dikirim. */
export function kosong(teks: string, p: Penerima) {
  const cek: Record<string, () => boolean> = {
    "{daftar_tanya}": () => !sekolahTodo(p).length,
    "{daftar_todo}": () => (p.todo ? !p.todo.length : !sekolahTodo(p).length),
    "{daftar_reviu}": () => !daftarReviu(p),
    "{daftar_sulit}": () => !daftarSulit(p),
    "{daftar_fasil}": () => !daftarFasil(p),
  };
  return Object.entries(cek).filter(([k, f]) => teks.includes(k) && f()).map(([k]) => k);
}

export function templateBawaan(jenis: JenisPenerima): Template[] {
  if (jenis === "fasil") {
    return [
      { kode: "tanya", judul: "Tanya kendala per sekolah", bawaan: true,
        ket: "Semua sekolah sekaligus, format Kendala / Tindak lanjut. Balasannya bisa langsung dibaca aplikasi.",
        teks: `${SALAM} Bapak/Ibu {nama}, izin menindaklanjuti progres pelaporan sekolah dampingan Bapak/Ibu.

Berikut laporan yang masih perlu dilengkapi:

{daftar_tanya}

Mohon dibantu mengisi *Kendala* dan *Tindak lanjut* untuk tiap sekolah (cukup isi titik-titiknya), supaya mudah kami rekap. ${TERIMA_KASIH}` },
      { kode: "ingat", judul: "Pengingat to-do", bawaan: true,
        ket: "Daftar yang perlu dilengkapi tanpa meminta jawaban per sekolah.",
        teks: `${SALAM} Bapak/Ibu {nama}, izin mengingatkan laporan sekolah dampingan yang masih perlu dilengkapi di aplikasi:

{daftar_todo}

Mohon dibantu mendampingi sekolah agar laporannya segera lengkap. ${TERIMA_KASIH}` },
      { kode: "reviu", judul: "Ingatkan reviu", bawaan: true,
        ket: "Hanya laporan yang sudah masuk dan menunggu reviu fasil.",
        teks: `${SALAM} Bapak/Ibu {nama}, izin menginformasikan laporan sekolah dampingan berikut sudah masuk dan menunggu reviu Bapak/Ibu:

{daftar_reviu}

Mohon dibantu segera direviu di aplikasi. ${TERIMA_KASIH}` },
      { kode: "tagih", judul: "Tagih informasi", bawaan: true,
        ket: "Untuk fasil yang belum menjawab pertanyaan sebelumnya.",
        teks: `${SALAM} Bapak/Ibu {nama}, mohon izin menindaklanjuti permintaan informasi yang sudah kami sampaikan sebelumnya.

Mohon kesediaan Bapak/Ibu untuk *segera* mengirimkan informasi tersebut *menggunakan format yang sudah kami kirimkan* (cukup disalin, lalu diisi per sekolah), agar data dapat kami rekap dengan tepat.

${TERIMA_KASIH}` },
      { kode: "format", judul: "Minta sesuai format", bawaan: true,
        ket: "Balasan fasil belum mengikuti format per sekolah.",
        teks: `Terima kasih atas informasinya, Bapak/Ibu {nama} 🙏

Mohon izin, agar data dapat kami rekap dengan tepat, mohon informasi tersebut *dikirim ulang sesuai format* berikut (diisi per sekolah):

{daftar_tanya}` },
      { kode: "info", judul: "Info / pengumuman", bawaan: true,
        ket: "Pesan bebas, mis. undangan grup atau link survei. Ganti isinya sesuai kebutuhan.",
        teks: `${SALAM} Bapak/Ibu {nama},

[tulis informasinya di sini]

${TERIMA_KASIH}` },
      { kode: "makasih", judul: "Terima kasih", bawaan: true, ket: "Menutup percakapan setelah fasil menjawab.",
        teks: "Terima kasih atas informasinya, Bapak/Ibu {nama}. Sudah kami catat. Mohon terus dampingi sekolah binaan agar laporannya segera lengkap 🙏" },
    ];
  }
  if (jenis === "koor") {
    return [
      { kode: "sulit", judul: "Fasil sulit dihubungi", bawaan: true,
        ket: "Minta bantuan koordinator untuk fasil yang chatnya tidak sampai / tidak dibalas.",
        teks: `${SALAM} Bapak/Ibu {nama}, mohon izin. Kami dari tim monitoring ingin menyampaikan bahwa fasilitator berikut belum dapat kami hubungi untuk konfirmasi progres pelaporan sekolah dampingan:

{daftar_sulit}

Mohon bantuan Bapak/Ibu untuk mengingatkan fasilitator tersebut agar dapat merespons pesan kami. ${TERIMA_KASIH}` },
      { kode: "rekap", judul: "Rekap to-do fasil binaan", bawaan: true,
        ket: "Ringkasan per fasil: berapa sekolah yang laporannya belum lengkap.",
        teks: `${SALAM} Bapak/Ibu {nama}, izin menyampaikan rekap progres pelaporan sekolah dampingan fasilitator binaan Bapak/Ibu:

{daftar_fasil}

Mohon bantuan Bapak/Ibu untuk mendorong fasilitator agar laporan sekolah segera lengkap. ${TERIMA_KASIH}` },
      { kode: "info", judul: "Info / pengumuman", bawaan: true, ket: "Pesan bebas untuk koordinator.",
        teks: `${SALAM} Bapak/Ibu {nama},

[tulis informasinya di sini]

${TERIMA_KASIH}` },
    ];
  }
  return [
    { kode: "ingat", judul: "Pengingat laporan sekolah", bawaan: true,
      ket: "Ke kepala sekolah: laporan yang perlu dikirim/diunggah sekolah (tanpa tugas reviu fasil).",
      teks: `${SALAM} Bapak/Ibu {nama}, Kepala {sekolah}. Kami dari tim monitoring Revitalisasi SD 2026 ingin mengingatkan laporan yang masih perlu dilengkapi di aplikasi:

{daftar_todo}

Bila ada kendala, mohon dapat disampaikan melalui balasan pesan ini. ${TERIMA_KASIH}` },
    { kode: "info", judul: "Info / pengumuman", bawaan: true, ket: "Pesan bebas untuk kepala sekolah.",
      teks: `${SALAM} Bapak/Ibu {nama}, Kepala {sekolah}.

[tulis informasinya di sini]

${TERIMA_KASIH}` },
  ];
}

// ---------- membaca balasan ----------

export type JawabanSekolah = { no: number; judul: string; kendala: string; tl: string };

const RE_KEPALA = /^\s*(\d{1,3})\s*[.)]\s*(.*)$/;
const RE_KENDALA = /^\s*[•*\-]?\s*\*?kendala\*?\s*[:：=-]\s*(.*)$/i;
const RE_TL = /^\s*[•*\-]?\s*\*?(?:tindak\s*lanjut|tl|rencana(?:\s*tindak\s*lanjut)?)\*?\s*[:：=-]\s*(.*)$/i;

function bersih(s: string) {
  return s.replace(/\*/g, "").replace(/^\.{2,}$/, "").replace(/\s*\.{3,}\s*$/, "").trim();
}

/** "1. SD A … Kendala: x … Tindak lanjut: y" -> per nomor. Baris lanjutan ikut isian di atasnya. */
export function bacaBalasan(teks: string): JawabanSekolah[] {
  const out: JawabanSekolah[] = [];
  let cur: JawabanSekolah | null = null;
  let isian: "kendala" | "tl" | null = null;
  for (const baris of teks.replace(/\r/g, "").split("\n")) {
    const k = RE_KEPALA.exec(baris);
    if (k && !RE_KENDALA.test(k[2]) && !RE_TL.test(k[2])) {
      cur = { no: Number(k[1]), judul: bersih(k[2]), kendala: "", tl: "" };
      out.push(cur);
      isian = null;
      continue;
    }
    if (!cur) continue;
    const a = RE_KENDALA.exec(baris);
    const b = RE_TL.exec(baris);
    if (a) { cur.kendala = bersih(a[1]); isian = "kendala"; continue; }
    if (b) { cur.tl = bersih(b[1]); isian = "tl"; continue; }
    const lanjut = bersih(baris);
    if (isian && lanjut && !/^[•]/.test(baris.trim())) cur[isian] = `${cur[isian]} ${lanjut}`.trim();
  }
  return out.filter((x) => x.kendala || x.tl);
}

function norm(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/** Cocokkan jawaban ke sekolah: lewat nama di baris judul, bila tidak ketemu lewat nomor urut. */
export function cocokkan<T extends { nama: string }>(jawab: JawabanSekolah[], sekolah: T[]) {
  const out = new Map<T, JawabanSekolah>();
  for (const j of jawab) {
    const n = norm(j.judul);
    const byNama = n ? sekolah.find((s) => { const m = norm(s.nama); return m && (n.includes(m) || m.includes(n)); })
      : undefined;
    const s = byNama ?? sekolah[j.no - 1];
    if (s && !out.has(s)) out.set(s, j);
  }
  return out;
}

/** Pilihan dropdown Kendala yang paling cocok dengan teks jawaban, atau teks aslinya. */
export function pilihKendala(teks: string, opsi: string[]) {
  const t = norm(teks);
  if (!t) return "";
  if (/^(tidak ada|tdk ada|aman|lancar|ok|nihil|-)$/.test(t)) {
    return opsi.find((o) => norm(o).includes("tidak ada kendala")) ?? teks;
  }
  let terbaik = "";
  let skor = 0;
  const kata = new Set(t.split(" ").filter((k) => k.length > 3));
  for (const o of opsi) {
    const ko = norm(o.replace(/^\d+\.\s*/, "")).split(" ").filter((k) => k.length > 3);
    if (!ko.length) continue;
    const s = ko.filter((k) => kata.has(k)).length / ko.length;
    if (s > skor) { skor = s; terbaik = o; }
  }
  return skor >= 0.6 ? terbaik : teks;
}
