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
const LINK_APLIKASI = "https://revitsd.kemendikdasmen.go.id/rolelogin";
const KOP = "📌 *INFORMASI & PENGINGAT RESMI | TIM MONITORING*\nSubdit Sarpras – Direktorat SD, Kemendikdasmen";
const PENUTUP_BC = `🔗 *Akses Aplikasi Revitalisasi SD:*
${LINK_APLIKASI}

Apabila terdapat kendala teknis di lapangan, mohon segera dikoordinasikan dengan Tim Monitoring.

Terima kasih atas perhatian, pendampingan, dan kerja samanya. 🙏🏻

Salam,
Tim Monitoring`;

/** Variabel yang bisa dipakai di pesan, per jenis penerima. */
export const VARIABEL: Record<JenisPenerima, { kode: string; arti: string }[]> = {
  fasil: [
    { kode: "{salam}", arti: "Selamat pagi/siang/sore/malam (otomatis saat dikirim)" },
    { kode: "{nama}", arti: "Nama fasil" },
    { kode: "{jumlah_sekolah}", arti: "Jumlah sekolah yang masih punya to-do" },
    { kode: "{daftar_tanya}", arti: "Daftar sekolah + to-do + baris Kendala/Tindak lanjut" },
    { kode: "{daftar_todo}", arti: "Daftar sekolah + to-do (tanpa isian)" },
    { kode: "{daftar_reviu}", arti: "Laporan yang menunggu reviu fasil" },
    { kode: "{daftar_sekolah}", arti: "Sekolah yang punya to-do: nama (NPSN) - kab/kota | angkatan" },
    { kode: "{sekolah_lp_belum}", arti: "Sekolah yang belum submit Lap. Pendahuluan (NPSN, kab/kota, angkatan)" },
    { kode: "{sekolah_lp_revisi}", arti: "Sekolah yang Lap. Pendahuluannya berstatus Revisi" },
    { kode: "{sekolah_lp_reviu}", arti: "Sekolah yang Lap. Pendahuluannya menunggu reviu fasil, dengan waktu tunggu" },
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
    `${i + 1}. *${x.nama}*\n${x.todo.map((t) => `   ${poin(t, true)}\n   Kendala: ...\n   Tindak lanjut: ...`).join("\n")}`,
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

type SekolahTodo = NonNullable<Penerima["sekolah"]>[number];

function barisSekolah(x: SekolahTodo, i: number, tambahan = "") {
  const kab = x.kab ? ` - ${x.kab}` : "";
  const ak = x.angkatan ? ` | Angkatan ${x.angkatan}` : "";
  return `${i + 1}. ${x.nama}${x.npsn ? ` (NPSN: ${x.npsn})` : ""}${kab}${ak}${tambahan}`;
}

/** Daftar sekolah (format BC) yang punya to-do cocok dengan `pilih`. */
function daftarBc(p: Penerima, pilih: (t: TodoRingkas) => boolean, tambahan?: (t: TodoRingkas) => string) {
  const xs = sekolahTodo(p).map((x) => ({ x, t: x.todo.find(pilih) })).filter((y) => y.t);
  return xs.map(({ x, t }, i) => barisSekolah(x, i, tambahan && t ? tambahan(t) : "")).join("\n");
}

const LP_BELUM = (t: TodoRingkas) => t.kode === "lp";
const LP_REVISI = (t: TodoRingkas) => t.kode === "lp_rev" && /revisi/i.test(t.detail);
const LP_REVIU = (t: TodoRingkas) => t.kode === "lp_rev" && !/revisi/i.test(t.detail);
const TUNGGU = (t: TodoRingkas) => (t.tunggu != null ? ` | Waktu tunggu reviu: ${Math.round(t.tunggu)} hari` : "");

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

/** Penerima yang dipersempit ke komponen papan LK yang dipilih (boleh lebih dari satu): hanya sekolah, to-do,
 *  dan fasil di komponen itu. Mengembalikan null bila penerima tidak punya apa pun di komponen tersebut. */
export function persempit(p: Penerima, komponen: string[]): Penerima | null {
  if (!komponen.length) return p;
  const jml = (posisi?: Record<string, number>) => komponen.reduce((n, k) => n + (posisi?.[k] ?? 0), 0);
  const n = jml(p.posisi);
  if (!n) return null;
  const kena = (t: TodoRingkas) => komponen.includes(t.posisi ?? "");
  return {
    ...p,
    perlu: n,
    sekolah: p.sekolah?.map((x) => ({ ...x, todo: x.todo.filter(kena) })).filter((x) => x.todo.length),
    todo: p.todo?.filter(kena),
    fasil: p.fasil?.filter((f) => jml(f.posisi)).map((f) => ({ ...f, perlu: jml(f.posisi) })),
  };
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
    "{daftar_sekolah}": () => sTodo.map((x, i) => barisSekolah(x, i)).join("\n"),
    "{sekolah_lp_belum}": () => daftarBc(p, LP_BELUM),
    "{sekolah_lp_revisi}": () => daftarBc(p, LP_REVISI),
    "{sekolah_lp_reviu}": () => daftarBc(p, LP_REVIU, TUNGGU),
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
    "{daftar_sekolah}": () => !sekolahTodo(p).length,
    "{sekolah_lp_belum}": () => !daftarBc(p, LP_BELUM),
    "{sekolah_lp_revisi}": () => !daftarBc(p, LP_REVISI),
    "{sekolah_lp_reviu}": () => !daftarBc(p, LP_REVIU),
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
      { kode: "bc_lp_belum", judul: "BC LP belum submit", bawaan: true,
        ket: "Broadcast resmi: daftar sekolah yang belum submit Laporan Pendahuluan (NPSN, kab/kota, angkatan).",
        teks: `${KOP}

{salam}, Bapak/Ibu {nama}. 🙏🏻

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Berdasarkan hasil pemantauan pada sistem Aplikasi Revitalisasi SD, sekolah dampingan Bapak/Ibu dari seluruh angkatan yang telah menyelesaikan penandatanganan PKS berikut tercatat belum melakukan submit Laporan Pendahuluan:

🏫 *Daftar Sekolah Binaan:*
{sekolah_lp_belum}

Mengingat Laporan Pendahuluan merupakan persyaratan administrasi penting untuk kelanjutan pelaksanaan dan tahapan berikutnya, mohon bantuan Bapak/Ibu Fasilitator untuk segera:
1. Mengingatkan dan mendampingi sekolah dalam menyusun berkas Laporan Pendahuluan.
2. Memastikan sekolah mengunggah dokumen dan menekan tombol Submit pada Aplikasi Revitalisasi SD.
3. Melakukan verifikasi terhadap dokumen yang telah diunggah oleh sekolah.

${PENUTUP_BC}` },
      { kode: "bc_lp_revisi", judul: "BC LP perlu revisi", bawaan: true,
        ket: "Broadcast resmi: sekolah yang sudah submit Laporan Pendahuluan tapi hasil reviunya Revisi.",
        teks: `${KOP}

{salam}, Bapak/Ibu {nama}. 🙏🏻

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Berdasarkan pemantauan pada Aplikasi Revitalisasi SD, sekolah dampingan Bapak/Ibu dari seluruh angkatan berikut sudah melakukan submit Laporan Pendahuluan, tetapi hasil reviunya masih berstatus *Revisi*:

🏫 *Daftar Sekolah yang Perlu Revisi:*
{sekolah_lp_revisi}

Mohon bantuan Bapak/Ibu Fasilitator untuk:
1. Meninjau kembali catatan hasil reviu Laporan Pendahuluan dan menyampaikan perbaikan yang diperlukan kepada sekolah dampingan.
2. Mendampingi sekolah agar memperbaiki atau melengkapi dokumen sesuai catatan, kemudian mengunggah dan melakukan submit ulang Laporan Pendahuluan.
3. Memastikan dokumen hasil perbaikan ditindaklanjuti dan diperiksa kembali sesuai alur reviu pada aplikasi.

${PENUTUP_BC.replace("kendala teknis di lapangan, mohon segera dikoordinasikan dengan", "kendala teknis atau administrasi, mohon segera berkoordinasi dengan")}` },
      { kode: "bc_lp_reviu", judul: "BC LP menunggu reviu", bawaan: true,
        ket: "Broadcast resmi: sekolah yang sudah submit Laporan Pendahuluan tapi belum direviu fasil, dengan waktu tunggu.",
        teks: `${KOP}

{salam}, Bapak/Ibu {nama}. 🙏🏻

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Berdasarkan hasil pemantauan pada Aplikasi Revitalisasi SD, sekolah dampingan Bapak/Ibu dari seluruh angkatan berikut telah melakukan submit Laporan Pendahuluan, namun status reviu Fasilitator masih tercatat *Belum*:

🏫 *Daftar Sekolah Menunggu Reviu:*
{sekolah_lp_reviu}

Mohon bantuan Bapak/Ibu Fasilitator untuk segera:
1. Memeriksa dan mereviu Laporan Pendahuluan yang telah disubmit oleh masing-masing sekolah dampingan.
2. Memberikan hasil reviu melalui aplikasi. Apabila diperlukan perbaikan dokumen, mohon cantumkan catatan revisi yang jelas agar sekolah dapat segera menindaklanjuti.
3. Memastikan hasil dan status reviu tercatat pada aplikasi serta mengoordinasikan tindak lanjut dengan sekolah terkait.

${PENUTUP_BC.replace("kendala teknis di lapangan, mohon segera dikoordinasikan dengan", "kendala teknis dalam proses reviu, mohon segera berkoordinasi dengan")}` },
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
      { kode: "bc_koor_lp", judul: "BC Koordinator: Laporan Pendahuluan", bawaan: true,
        ket: "Broadcast resmi ke Koordinator PTN tentang pendampingan dan verifikasi Laporan Pendahuluan.",
        teks: `📌 *INFORMASI RESMI | TIM MONITORING*
Subdit Sarpras – Direktorat SD, Kemendikdasmen

{salam},
Yth. Bapak/Ibu {nama} selaku Koordinator PTN.

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Mohon izin menyampaikan informasi terkait pendampingan penyusunan dan verifikasi Laporan Pendahuluan pada Aplikasi Revitalisasi SD:

1. 📄 *Kewajiban Laporan Pendahuluan:* Sekolah penerima bantuan diwajibkan menyusun dan mengunggah Laporan Pendahuluan (termasuk foto kondisi 0% dan jadwal pelaksanaan) sebagai syarat mutlak sebelum pekerjaan fisik dilanjutkan.

2. 🤝 *Pendampingan & Verifikasi:* Mohon bantuan Bapak/Ibu Koordinator untuk mengarahkan rekan-rekan Fasilitator agar memastikan sekolah dampingannya segera mengunggah dokumen serta melakukan verifikasi secara berkala di aplikasi.

3. 🔗 *Akses Sistem:* Pemantauan dan progres pelaporan dapat dipantau langsung melalui Aplikasi Revitalisasi SD pada tautan:
${LINK_APLIKASI}

Mohon kerja sama Bapak/Ibu untuk bersama-sama memantau dan mendampingi ketepatan waktu pelaporan di wilayah masing-masing.

Terima kasih atas perhatian dan kerja samanya. 🙏🏻

Salam,
Tim Monitoring` },
      { kode: "rekap", judul: "Rekap to-do fasil binaan", bawaan: true,
        ket: "Ringkasan per fasil: berapa sekolah yang laporannya belum lengkap.",
        teks: `${SALAM} Bapak/Ibu {nama}, izin menyampaikan rekap progres pelaporan sekolah dampingan fasilitator binaan Bapak/Ibu:

{daftar_fasil}

Mohon bantuan Bapak/Ibu untuk mendorong fasilitator agar laporan sekolah segera lengkap. ${TERIMA_KASIH}` },
      { kode: "sulit", judul: "Fasil sulit dihubungi", bawaan: true,
        ket: "Koordinator yang fasilnya hanya membaca chat, centang satu, atau tidak ada WA (dari WhatsApp minggu ini & Log Komunikasi).",
        teks: `${SALAM} Bapak/Ibu {nama}, mohon izin. Kami dari tim monitoring ingin menyampaikan bahwa fasilitator berikut belum dapat kami hubungi untuk konfirmasi progres pelaporan sekolah dampingan:

{daftar_sulit}

Mohon bantuan Bapak/Ibu untuk mengingatkan fasilitator tersebut agar dapat merespons pesan kami. ${TERIMA_KASIH}` },
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

export type IsianPoin = { judul: string; kendala: string; tl: string };
/** Jawaban satu sekolah. `kendala`/`tl` = isian di tingkat sekolah (format lama, satu untuk semua to-do);
 *  `poin` = isian per to-do (format "• To-do / Kendala / Tindak lanjut"). */
export type JawabanSekolah = { no: number; judul: string; kendala: string; tl: string; poin: IsianPoin[] };

const RE_KEPALA = /^\s*(\d{1,3})\s*[.)]\s*(.*)$/;
const RE_KENDALA = /^\s*[•*\-]?\s*\*?kendala\*?\s*[:：=-]\s*(.*)$/i;
const RE_TL = /^\s*[•*\-]?\s*\*?(?:tindak\s*lanjut|tl|rencana(?:\s*tindak\s*lanjut)?)\*?\s*[:：=-]\s*(.*)$/i;
const RE_POIN = /^\s*[•\-]\s*(.+)$/;

function bersih(s: string) {
  return s.replace(/\*/g, "").replace(/^\.{2,}$/, "").replace(/\s*\.{3,}\s*$/, "").trim();
}

/** "1. SD A / • To-do / Kendala: x / Tindak lanjut: y" -> per nomor sekolah, per to-do. Kendala/TL sebelum
 *  poin pertama berlaku untuk sekolah itu. Baris lanjutan ikut isian di atasnya. */
export function bacaBalasan(teks: string): JawabanSekolah[] {
  const out: JawabanSekolah[] = [];
  let cur: JawabanSekolah | null = null;
  let poin: IsianPoin | null = null;
  let isian: "kendala" | "tl" | null = null;
  for (const baris of teks.replace(/\r/g, "").split("\n")) {
    const k = RE_KEPALA.exec(baris);
    if (k && !RE_KENDALA.test(k[2]) && !RE_TL.test(k[2])) {
      cur = { no: Number(k[1]), judul: bersih(k[2]), kendala: "", tl: "", poin: [] };
      out.push(cur);
      poin = null;
      isian = null;
      continue;
    }
    if (!cur) continue;
    const a = RE_KENDALA.exec(baris);
    const b = RE_TL.exec(baris);
    const tuju: { kendala: string; tl: string } = poin ?? cur;
    if (a) { tuju.kendala = bersih(a[1]); isian = "kendala"; continue; }
    if (b) { tuju.tl = bersih(b[1]); isian = "tl"; continue; }
    const p = RE_POIN.exec(baris);
    if (p) { poin = { judul: bersih(p[1]), kendala: "", tl: "" }; cur.poin.push(poin); isian = null; continue; }
    const lanjut = bersih(baris);
    if (!baris.trim()) { isian = null; continue; } // baris kosong mengakhiri isian (mis. paragraf penutup)
    if (isian && lanjut) tuju[isian] = `${tuju[isian]} ${lanjut}`.trim();
  }
  for (const x of out) x.poin = x.poin.filter((p) => p.kendala || p.tl);
  return out.filter((x) => x.kendala || x.tl || x.poin.length);
}

function norm(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/** Isian untuk satu to-do: poin yang judulnya cocok, bila tidak ada isian tingkat sekolah, bila tidak ada dan
 *  hanya ada satu poin untuk satu to-do, poin itu. */
export function isianTodo(j: JawabanSekolah, judul: string, jumlahTodo: number): { kendala: string; tl: string } | null {
  const n = norm(judul);
  const p = n ? j.poin.find((x) => { const m = norm(x.judul); return m.startsWith(n) || (m.length > 8 && n.startsWith(m)); })
    : undefined;
  if (p) return p;
  if (j.kendala || j.tl) return { kendala: j.kendala, tl: j.tl };
  if (j.poin.length === 1 && jumlahTodo === 1) return j.poin[0];
  return null;
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

/** Pilihan dropdown Kendala yang cocok dengan teks jawaban, atau "" bila tidak ada yang cocok. */
export function pilihKendala(teks: string, opsi: string[]) {
  const t = norm(teks);
  if (!t) return "";
  const persis = opsi.find((o) => norm(o) === t || norm(o.replace(/^\d+\.\s*/, "")) === t);
  if (persis) return persis;
  const no = /^(\d{1,2})\s*[.)]?$/.exec(teks.trim()) ?? /^(\d{1,2})\s*[.)]\s/.exec(teks.trim());
  if (no) { const o = opsi.find((x) => x.startsWith(`${no[1]}.`)); if (o) return o; }
  if (/^(tidak ada|tdk ada|ga ada|gak ada|tidak ada kendala|aman|lancar|ok|nihil|belum ada|-)$/.test(t)) {
    return opsi.find((o) => norm(o).includes("tidak ada kendala")) ?? "";
  }
  if (/^lainnya\b/.test(t)) return opsi.find((o) => /lainnya/i.test(o)) ?? "";
  let terbaik = "";
  let skor = 0;
  const kata = new Set(t.split(" ").filter((k) => k.length > 3));
  for (const o of opsi) {
    const ko = norm(o.replace(/^\d+\.\s*/, "")).split(" ").filter((k) => k.length > 3);
    if (!ko.length) continue;
    const s = ko.filter((k) => kata.has(k)).length / ko.length;
    if (s > skor) { skor = s; terbaik = o; }
  }
  return skor >= 0.6 ? terbaik : "";
}

/** Kendala + Tindak lanjut siap isi: kendala yang ada di dropdown dipakai apa adanya; yang tidak ada jadi
 *  pilihan "Lainnya" dan teksnya digabung ke depan Tindak lanjut ("Dana sudah cair, Sedang proses …"). */
export function isiKendala(kendala: string, tl: string, opsi: string[]): { kendala: string; tl: string } {
  const k = kendala.split(/\s+/).filter(Boolean).join(" ");
  const t = tl.trim();
  if (!k) return { kendala: "", tl: t };
  const cocok = pilihKendala(k, opsi);
  if (cocok) return { kendala: cocok, tl: t };
  const lain = opsi.find((o) => /lainnya/i.test(o));
  if (!lain) return { kendala: k, tl: t };
  return { kendala: lain, tl: gabungKoma(k, t) };
}

function gabungKoma(a: string, b: string) {
  if (!b) return a;
  if (norm(b).startsWith(norm(a))) return b;
  return `${a.replace(/[\s,.;]+$/, "")}, ${b}`;
}

// ---------- hubungi koordinator dari panel fasil ----------

type FasilUntukKoor = {
  nama: string; koor: string; ptn: string; todo_fasil: number; tanpa_progres: boolean;
  sekolah_detail: { nama: string; todo: { judul: string; detail: string; pelaku: "sekolah" | "fasil" }[] }[];
};

/** Template WhatsApp ke koordinator tentang satu fasil (sudah terisi, siap kirim). */
export type SekolahUntukPesan = {
  nama: string; kepsek: string; todo: { judul: string; pelaku: string }[];
};

/** Pesan ke kepala sekolah: pengingat to-do sekolah (yang dikerjakan sekolah) dan info bebas. Fasil disebut supaya
 *  tidak merasa dilangkahi. */
export function templateSekolah(x: SekolahUntukPesan, fasil: string, salam = salamSekarang()): Template[] {
  const sapa = x.kepsek ? `Bapak/Ibu ${x.kepsek}` : "Bapak/Ibu Kepala Sekolah";
  const sekolah = `*${x.nama}*`;
  const tugas = x.todo.filter((t) => t.pelaku !== "fasil");
  const cc = fasil ? ` Hal ini juga sudah kami koordinasikan dengan fasilitator sekolah, *${fasil}*.` : "";
  const out: Template[] = [];
  if (tugas.length) {
    out.push({ kode: "todo_sekolah", judul: "Pengingat laporan sekolah", bawaan: true,
      ket: "Laporan yang masih perlu dikirim / diunggah oleh sekolah.",
      teks: `${salam} ${sapa}, Kepala ${sekolah}. Kami dari tim monitoring Revitalisasi SD 2026 izin mengingatkan, berdasarkan data kami laporan berikut masih perlu dilengkapi oleh sekolah:

${tugas.map((t, i) => `${i + 1}. ${t.judul}`).join("\n")}

Mohon bantuan ${sapa} agar laporan tersebut dapat segera dilengkapi.${cc} ${TERIMA_KASIH}` });
  }
  out.push({ kode: "info_sekolah", judul: "Info / pengumuman", bawaan: true,
    ket: "Teks bebas: ganti bagian dalam kurung siku.",
    teks: `${salam} ${sapa}, Kepala ${sekolah}. Kami dari tim monitoring Revitalisasi SD 2026 izin menyampaikan informasi:

[tulis informasinya di sini]
${cc ? `\n${cc.trim()}` : ""}
${TERIMA_KASIH}` });
  return out;
}

export function templateKoorFasil(f: FasilUntukKoor, salam = salamSekarang()): Template[] {
  const sapa = f.koor ? `Bapak/Ibu ${f.koor}` : "Bapak/Ibu Koordinator";
  const sekolah = f.sekolah_detail.filter((x) => x.todo.length).slice().sort((a, b) => a.nama.localeCompare(b.nama));
  const daftar = sekolah.slice(0, 15).map((x, i) => `${i + 1}. *${x.nama}*: ${x.todo.map((t) => t.judul).join(", ")}`)
    .join("\n") + (sekolah.length > 15 ? `\n… dan ${sekolah.length - 15} sekolah lainnya` : "");
  const reviu = f.sekolah_detail.flatMap((x) => x.todo.filter((t) => t.pelaku === "fasil").map((t) => `• ${x.nama}: ${t.judul}`));
  const siapa = `fasilitator *${f.nama}*${f.ptn ? ` (${f.ptn})` : ""}`;
  const out: Template[] = [
    { kode: "sulit", judul: "Fasil tidak membalas", bawaan: true,
      ket: "Chat ke fasil hanya dibaca, tidak sampai, atau tidak dibalas.",
      teks: `${salam} ${sapa}, mohon izin. Kami dari tim monitoring Revitalisasi SD 2026 ingin meminta bantuan terkait ${siapa}. Sudah beberapa kali kami hubungi, namun belum mendapat respons.

${sekolah.length ? `Sekolah dampingan beliau yang laporannya masih perlu dilengkapi:\n\n${daftar}\n\n` : ""}Mohon bantuan ${sapa} untuk mengingatkan beliau agar dapat membalas pesan kami. ${TERIMA_KASIH}` },
  ];
  if (sekolah.length) {
    out.push({ kode: "macet", judul: "Laporan tidak bergerak", bawaan: true,
      ket: "Fasil merespons, tapi laporan sekolahnya belum bertambah.",
      teks: `${salam} ${sapa}, mohon izin. Kami ingin menyampaikan bahwa ${siapa} sudah merespons pesan kami, namun laporan sekolah dampingannya belum bertambah sejak cutoff sebelumnya:

${daftar}

Mohon bantuan ${sapa} untuk mendorong agar laporan tersebut segera dilengkapi. ${TERIMA_KASIH}` });
  }
  if (reviu.length) {
    out.push({ kode: "reviu", judul: "Reviu menunggu fasil", bawaan: true,
      ket: "Laporan sekolah sudah masuk, tapi belum direviu fasil.",
      teks: `${salam} ${sapa}, mohon izin. Laporan sekolah dampingan ${siapa} sudah masuk dan menunggu reviu:

${reviu.slice(0, 15).join("\n")}${reviu.length > 15 ? `\n… dan ${reviu.length - 15} lainnya` : ""}

Mohon bantuan ${sapa} untuk mengingatkan beliau agar segera mereviu. ${TERIMA_KASIH}` });
  }
  out.push({ kode: "info", judul: "Pesan bebas", bawaan: true, ket: "Tulis sendiri pesannya.",
    teks: `${salam} ${sapa}, mohon izin. Terkait ${siapa}:\n\n[tulis pesannya di sini]\n\n${TERIMA_KASIH}` });
  return out;
}
