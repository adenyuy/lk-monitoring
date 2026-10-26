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

const GRUP: { judul: string; isi: T[] }[] = [
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
            <p>Di <Link href="/today/">Hari ini</Link> muncul pengingat kuning <b>Sesi n terlewat</b> yang menyebut berapa
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
            <p>Pagi harinya Hari ini menampilkan pengingat <b>Lanjutan dari kemarin</b> dengan jumlah fasil yang masih
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
            <p>Supaya tidak ada yang terlupa, Hari ini menampilkan daftar <b>fasil yang sudah membalas tapi isian LK-nya
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
          <p>Tidak otomatis. Perubahannya tercatat di <Link href="/rekap/#perubahan">Log perubahan</Link>. Bila memang perlu
            kirim susulan, buka panel fasil lalu tekan <b>Kirim ulang broadcast</b>. Pesannya ikut di sesi berikutnya.</p>
        ),
      },
      {
        id: "tidak-di-broadcast",
        q: "Ada fasil di LK yang tidak ada di Broadcast. Kenapa?",
        a: (
          <p>Broadcast hanya berisi fasil yang punya sekolah sasaran P1. Fasil lain tetap muncul di{" "}
            <Link href="/rekap/">Rekap</Link> dan tetap bisa dichat dari panelnya.</p>
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
        q: "Kenapa Log perubahan masih kosong?",
        a: (
          <p>Bacaan pertama Broadcast dan LK hanya dipakai sebagai patokan. Catatan baru muncul setelah ada yang berbeda
            dari bacaan sebelumnya. Pilih tanggal di kalender untuk melihat perubahan hari-hari sebelumnya, dikelompokkan
            per sesi. Log disimpan 90 hari.</p>
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
            halaman, membuka Log perubahan, Panduan, atau halaman ini.</p>
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

  // Buka pertanyaan dari tautan (#sesi-terlewat dan sebagainya)
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (!id) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBuka(id);
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
  }, []);

  return (
    <div className={s.page}>
      <header className={s.head}>
        <h1>Tanya jawab</h1>
        <p>Hal yang sering ditanyakan soal sesi, antrean kirim, chat, dan isian LK.</p>
      </header>
      {GRUP.map((g, gi) => (
        <section key={g.judul} className={s.grup} aria-labelledby={`faq-g${gi}`}>
          <h2 id={`faq-g${gi}`}>{g.judul}</h2>
          <div className={s.list}>
            {g.isi.map((t) => (
              <details key={t.id} id={t.id} className={s.item} open={buka === t.id || undefined}>
                <summary>{t.q}</summary>
                <div className={s.ans}>{t.a}</div>
              </details>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
