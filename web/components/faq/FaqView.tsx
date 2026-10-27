"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import s from "./faq.module.css";

type T = { id: string; q: string; a: ReactNode };

const SESI = [
  { no: 1, kuota: 10 },
  { no: 2, kuota: 10 },
  { no: 3, kuota: 15 },
  { no: 4, kuota: 15 },
  { no: 5, kuota: 10 },
];

/** Contoh satu hari: sesi 1 baru terkirim 4, sisa antrean ikut sesi berikutnya sampai batas harian 40. */
function ContohHari() {
  const terkirim = [4, 10, 15, 11, 0];
  return (
    <figure className={s.contoh}>
      <div className={s.contohRow}>
        {SESI.map((x, i) => (
          <div key={x.no} className={s.contohSesi} style={{ flexGrow: x.kuota }}>
            <div className={s.contohBar} aria-hidden="true">
              {Array.from({ length: x.kuota }, (_, k) => (
                <i key={k} className={k < terkirim[i] ? s.slotIsi : s.slotKosong} />
              ))}
            </div>
            <b>Sesi {x.no}</b>
            <small>{terkirim[i]} dari {x.kuota}</small>
          </div>
        ))}
      </div>
      <figcaption>
        Contoh: sesi 1 baru 4 terkirim lalu terlewat. 6 slot sesi 1 hangus, tapi fasilnya tetap di antrean dan ikut di
        sesi 2–4. Hari itu tetap mencapai batas harian 40 dari total 60 slot, jadi sesi 5 tidak terpakai.
      </figcaption>
    </figure>
  );
}

const MINGGU = [
  { hari: "Senin", kerja: "Broadcast", lk: "Senin–Rabu" },
  { hari: "Selasa", kerja: "Broadcast", lk: "Senin–Rabu" },
  { hari: "Rabu", kerja: "Tindak lanjut", lk: "Rabu–Jumat" },
  { hari: "Kamis", kerja: "Tindak lanjut", lk: "Rabu–Jumat" },
  { hari: "Jumat", kerja: "Tindak lanjut", lk: "Rabu–Jumat" },
];

/** Contoh satu minggu untuk 69 fasil dengan batas harian 40. */
function ContohMinggu() {
  return (
    <figure className={s.contoh}>
      <ol className={s.minggu}>
        {MINGGU.map((m, i) => (
          <li key={m.hari} className={m.kerja === "Broadcast" ? s.mgKirim : s.mgTl}>
            <b>{m.hari}</b>
            <span>{m.kerja === "Broadcast" ? (i === 0 ? "Broadcast 40 fasil" : "Broadcast 29 fasil") : "Chat tindak lanjut"}</span>
            <small>Isi LK sesi {m.lk}</small>
          </li>
        ))}
      </ol>
      <figcaption>
        Contoh 69 fasil dengan batas 40 per hari: Broadcast selesai Selasa. Rabu sampai Jumat dipakai untuk menanyakan
        isian LK ke fasil yang belum membalas atau belum lengkap. Senin berikutnya siklus diulang dengan WEEK baru.
      </figcaption>
    </figure>
  );
}

const GRUP: { judul: string; isi: T[] }[] = [
  {
    judul: "Alur mingguan",
    isi: [
      {
        id: "alur-minggu",
        q: "Seperti apa alur kerja satu minggu?",
        a: (
          <>
            <p>Awal minggu untuk <b>Broadcast</b>: pesan progres dikirim ke semua fasil di sheet Broadcast, dibagi per
              sesi sampai batas harian. Sisa minggu untuk <b>tindak lanjut</b>: chat fasil satu per satu, tanyakan alasan
              sekolah yang belum submit atau progresnya di bawah 50%, lalu isi LK.</p>
            <ContohMinggu />
          </>
        ),
      },
      {
        id: "hari-ketiga",
        q: "Broadcast sudah terkirim semua dalam dua hari. Hari ketiga ngapain?",
        a: (
          <>
            <p>Tindak lanjut. Tombol bulat menampilkan notifikasi <b>Broadcast minggu ini sudah terkirim ke semua
              fasil</b> dan daftar fasil yang perlu dichat lagi: yang sudah membalas tapi isian LK-nya belum lengkap
              ditaruh paling atas, lalu yang belum membalas.</p>
            <p>Klik nama fasil, pakai template <b>Tanya belum submit</b>, <b>Tanya progres</b>, atau <b>Tanya belum
              reviu</b>, lalu isi jawabannya di panel LK (kolom sesi Rabu–Jumat). Broadcast tidak dikirim ulang otomatis
              sampai Senin.</p>
          </>
        ),
      },
      {
        id: "week-2",
        q: "Bagaimana dengan WEEK 2, WEEK 3, dan seterusnya?",
        a: (
          <>
            <p>Siklusnya sama setiap minggu. Begitu admin membuat tab <b>WEEK n</b> baru di LK, aplikasi otomatis
              memakai tab itu untuk Hari ini, Rekap, dan isian LK. Perpindahannya tercatat di <Link href="/log/">Log</Link>.</p>
            <p>Hari Senin semua fasil di sheet Broadcast masuk antrean lagi. Isi pesannya mengikuti data progres terbaru
              di sheet, jadi pesan minggu kedua memang membahas progres yang baru. Fasil yang semua sekolahnya sudah
              selesai biasanya tidak ada lagi di Broadcast, jadi tidak dikirimi.</p>
          </>
        ),
      },
    ],
  },
  {
    judul: "Sesi dan antrean kirim",
    isi: [
      {
        id: "sesi-terlewat",
        q: "Sesinya sudah lewat, tapi belum semua fasil dikirimi. Fasilnya hilang?",
        a: (
          <>
            <p>Tidak. Fasil yang belum dikirimi tetap di antrean dan jadi yang pertama dikirim di sesi berikutnya, begitu
              Anda menekan <b>Kirim</b> lagi. Aplikasi tidak mengirim sendiri tanpa ditekan.</p>
            <p>Tombol bulat menampilkan notifikasi <b>Sesi n terlewat</b> yang menyebut berapa
              pesan masih bisa dikirim hari itu.</p>
          </>
        ),
      },
      {
        id: "kuota",
        q: "Kuota sesi yang tidak terpakai pindah ke sesi berikutnya?",
        a: (
          <>
            <p>Tidak menumpuk. Sesi 2 tetap paling banyak 10 pesan walaupun sesi 1 kosong, supaya jeda antarpesan tetap
              wajar dan nomor tidak diblokir.</p>
            <p>Total kuota lima sesi 60, sedangkan batas harian 40, jadi satu sesi yang terlewat biasanya masih bisa dikejar
              di sesi lain di hari yang sama.</p>
            <ContohHari />
          </>
        ),
      },
      {
        id: "besok",
        q: "Bagaimana dengan besok harinya?",
        a: (
          <>
            <p>Kuota tiap sesi dan batas harian mulai dari nol lagi. Antrean melanjutkan fasil yang <b>belum dikirimi minggu
              ini</b>. Fasil yang sudah dikirimi minggu ini tidak dikirimi lagi, walaupun isi Broadcast-nya berubah.</p>
            <p>Pagi harinya tombol bulat menampilkan notifikasi <b>Lanjutan dari kemarin</b> dengan jumlah fasil yang masih
              menunggu.</p>
          </>
        ),
      },
      {
        id: "senin",
        q: "Apa yang berubah di hari Senin?",
        a: (
          <p>Hitungan &quot;sudah dikirimi&quot; berlaku per minggu, Senin sampai Minggu. Hari Senin semua fasil di Broadcast
            masuk antrean lagi, dan isian LK pindah ke kolom sesi Senin–Rabu (P–U).</p>
        ),
      },
      {
        id: "luar-jam",
        q: "Bisakah mengirim Broadcast di luar jam sesi atau di akhir pekan?",
        a: (
          <p>Tidak. Tombol Kirim hanya aktif pukul 10.00–22.00 pada Senin–Jumat. Di luar itu kartu Sekarang dan tombol bulat
            menunjukkan kapan sesi berikutnya mulai. Membalas chat dan mengisi LK tetap bisa kapan saja.</p>
        ),
      },
      {
        id: "mati",
        q: "Laptop mati atau aplikasi tertutup di tengah sesi. Bagaimana?",
        a: (
          <p>Pengiriman berhenti, dan pesan yang sudah terkirim tetap tercatat. Buka lagi <b>LK Monitoring</b>, lalu tekan
            Kirim. Aplikasi melanjutkan dari fasil yang belum dikirimi, selama masih di jam sesi.</p>
        ),
      },
    ],
  },
  {
    judul: "Chat dan isian LK",
    isi: [
      {
        id: "chat-lewat-sesi",
        q: "Sesi sudah lewat, tapi saya masih mau chat fasil. Boleh?",
        a: (
          <>
            <p>Boleh. Membaca dan membalas chat serta mengisi LK tidak terikat jam sesi dan tidak memakai kuota sesi.
              Chat hanya dikunci sementara saat pengiriman Broadcast sedang berjalan. Tekan <b>Berhenti</b> atau tunggu
              sampai selesai.</p>
            <p>Supaya tidak ada yang terlupa, notifikasi di tombol bulat menampilkan daftar <b>fasil yang sudah membalas tapi isian LK-nya
              belum lengkap</b>, lalu yang belum membalas. Klik namanya untuk membuka chat dan LK-nya.</p>
          </>
        ),
      },
      {
        id: "blok-lk",
        q: "Isian LK masuk ke kolom sesi yang mana?",
        a: (
          <p>Senin dan Selasa otomatis ke sesi <b>Senin–Rabu</b> (kolom P–U). Rabu sampai Jumat ke sesi <b>Rabu–Jumat</b>
            (kolom V–AA). Anda bisa menggantinya di panel LK. Status komunikasi diisi sekali per fasil untuk semua
            sekolahnya.</p>
        ),
      },
      {
        id: "chat-hp",
        q: "Saya membalas fasil lewat HP. Apakah tercatat?",
        a: (
          <p>Chat dari HP ikut tampil di panel WhatsApp karena tersinkron dengan WhatsApp Web. Bila tahapnya belum
            tercentang otomatis, klik tahap itu di atas panel fasil untuk mencentangnya sendiri.</p>
        ),
      },
    ],
  },
  {
    judul: "Broadcast dan data",
    isi: [
      {
        id: "broadcast-berubah",
        q: "Isi Broadcast berubah setelah pesannya terkirim. Dikirim ulang?",
        a: (
          <p>Tidak otomatis. Perubahannya tercatat di <Link href="/log/">Log</Link>. Bila memang perlu
            kirim susulan, buka panel fasil lalu tekan <b>Kirim ulang broadcast</b>. Pesannya ikut di sesi berikutnya.</p>
        ),
      },
      {
        id: "tidak-di-broadcast",
        q: "Ada fasil di LK yang tidak ada di Broadcast. Bagaimana menghubunginya?",
        a: (
          <>
            <p>Broadcast hanya berisi fasil sasaran P1 dari sheet Broadcast. Fasil lain (misalnya yang sekolahnya P2, P3,
              atau P1 dengan progres sudah 50% atau lebih) tidak dikirimi Broadcast otomatis, jadi dihubungi lewat chat
              manual.</p>
            <p>Mereka tetap terpantau: tombol bulat menampilkan notifikasi <b>fasil di luar Broadcast belum dihubungi</b>
              beserta daftarnya. Begitu Anda mengirim chat dari panel fasil, fasil itu dihitung sudah dihubungi dan
              balasannya ikut dicek otomatis, sama seperti fasil Broadcast.</p>
          </>
        ),
      },
      {
        id: "warna",
        q: "Apa arti warna di sheet Broadcast P1?",
        a: (
          <ul>
            <li><b>Hijau</b>: pesan terkirim dan sampai (centang dua).</li>
            <li><b>Kuning</b>: pesan terkirim, baru centang satu.</li>
            <li><b>Merah</b>: nomor tidak terdaftar di WhatsApp. Periksa nomornya di sheet.</li>
          </ul>
        ),
      },
      {
        id: "log",
        q: "Kenapa Log masih kosong?",
        a: (
          <p>Bacaan pertama Broadcast dan LK hanya dipakai sebagai patokan. Catatan baru muncul setelah ada yang berbeda
            dari bacaan sebelumnya. Riwayat per fasil (Broadcast terkirim, dibaca, dibalas, LK diisi) mulai tercatat sejak
            versi ini. Pilih tanggal di kalender untuk melihat hari-hari sebelumnya. Log disimpan 90 hari.</p>
        ),
      },
    ],
  },
  {
    judul: "Aplikasi",
    isi: [
      {
        id: "tombol-bulat",
        q: "Tombol bulat di layar menghalangi. Bisa dipindah?",
        a: (
          <p>Bisa. Seret ke mana saja, nanti menempel ke tepi kiri atau kanan. Posisinya diingat. Ketuk sekali untuk pindah
            halaman, melihat notifikasi, membuka Panduan, atau halaman ini.</p>
        ),
      },
      {
        id: "pembaruan",
        q: "Bagaimana memperbarui aplikasi?",
        a: (
          <p>Saat admin merilis versi baru, muncul banner biru <b>Versi baru tersedia</b>. Tekan <b>Perbarui
            sekarang</b>: aplikasi mulai ulang sekitar satu menit lalu halaman memuat ulang sendiri. Setelah itu tekan Buka
            WhatsApp lagi (tidak perlu scan QR). Pembaruan ditolak selama Broadcast sedang dikirim.</p>
        ),
      },
      {
        id: "cache",
        q: "Kalau cache browser dihapus, data saya hilang?",
        a: (
          <>
            <p>Tidak. Data penting tersimpan di laptop di folder <b>%APPDATA%\LKMonitoring</b>, bukan di browser:
              login Google, riwayat kirim, log, dan sesi WhatsApp. Isian LK tersimpan di sheet.</p>
            <p>Yang hilang hanya kenyamanan tampilan: posisi tombol bulat, notifikasi yang sudah ditandai
              &quot;Mengerti&quot;, dan tanda log sudah dilihat.</p>
            <p><b>Jangan hapus folder %APPDATA%\LKMonitoring</b> di tengah minggu. Aplikasi akan lupa siapa yang sudah
              dikirimi minggu ini, sehingga Broadcast bisa terkirim dua kali, dan Anda harus login serta scan QR ulang.</p>
          </>
        ),
      },
      {
        id: "restart",
        q: "Muncul pesan kuning “Server aplikasi perlu dijalankan ulang”.",
        a: (
          <p>Klik dua kali <b>stop.bat</b> di folder aplikasi, lalu buka lagi <b>LK Monitoring</b> dari Desktop.</p>
        ),
      },
    ],
  },
];

export function FaqView() {
  const [buka, setBuka] = useState<string | null>(null);
  const [cari, setCari] = useState("");
  const [grup, setGrup] = useState<string | null>(null);

  // Buka pertanyaan dari tautan (#sesi-terlewat dan sebagainya)
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (!id) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBuka(id);
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
  }, []);

  const q = cari.trim().toLowerCase();
  const tampil = GRUP
    .filter((g) => !grup || g.judul === grup)
    .map((g) => ({ ...g, isi: g.isi.filter((x) => !q || x.q.toLowerCase().includes(q)) }))
    .filter((g) => g.isi.length);

  return (
    <div className={s.page}>
      <header className={s.head}>
        <h1>Tanya jawab</h1>
        <p>Hal yang sering ditanyakan soal alur mingguan, sesi, chat, dan isian LK. Klik kartu untuk membaca jawabannya.</p>
      </header>

      <div className={s.tools}>
        <input type="search" className={s.search} placeholder="Cari pertanyaan" value={cari}
          onChange={(e) => setCari(e.target.value)} aria-label="Cari pertanyaan" />
        <div className={s.chips} role="group" aria-label="Topik">
          <button type="button" aria-pressed={!grup} onClick={() => setGrup(null)}>Semua</button>
          {GRUP.map((g) => (
            <button key={g.judul} type="button" aria-pressed={grup === g.judul} onClick={() => setGrup(g.judul)}>
              {g.judul}
            </button>
          ))}
        </div>
      </div>

      {tampil.length === 0 && <p className={s.kosong}>Tidak ada pertanyaan yang cocok dengan “{cari}”.</p>}
      {tampil.map((g, gi) => (
        <section key={g.judul} className={s.grup} aria-labelledby={`faq-g${gi}`}>
          <h2 id={`faq-g${gi}`}>{g.judul}</h2>
          <div className={s.cards}>
            {g.isi.map((t) => {
              const terbuka = buka === t.id;
              return (
                <article key={t.id} id={t.id} className={`${s.cardQ} ${terbuka ? s.cardOpen : ""}`}>
                  <button type="button" className={s.qBtn} aria-expanded={terbuka}
                    onClick={() => setBuka(terbuka ? null : t.id)}>
                    <span className={s.qMark} aria-hidden="true">?</span>
                    <span className={s.qText}>{t.q}</span>
                    <span className={s.qChev} aria-hidden="true" />
                  </button>
                  {terbuka && <div className={s.ans}>{t.a}</div>}
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
