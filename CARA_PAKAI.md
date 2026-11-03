# Cara Pakai LK Monitoring

Aplikasi ini berjalan di laptop masing-masing dan dibuka lewat browser. Pesan WhatsApp dikirim dari **nomor WhatsApp kamu sendiri**, satu per satu per sesi, supaya aman dari blokir.

## 1. Pasang (sekali saja)

Yang perlu disiapkan:

- Laptop Windows 10/11 dengan internet.
- File **`lk-monitoring.json`** dari admin. Isinya izin aplikasi dan alamat sheet tim: jangan dibagikan ke orang lain.
- Email Google kamu sudah didaftarkan admin. Kalau belum, kamu akan melihat pesan "belum terdaftar".

Langkah:

1. Unduh **`install.bat`** dari admin, lalu klik dua kali.
2. Bila Windows bertanya "Windows protected your PC", pilih **More info → Run anyway**.
3. Tunggu sampai selesai (5–15 menit pertama kali). Git, Python, dan Google Chrome dipasang otomatis bila belum ada.
4. Aplikasi terbuka di browser, dan di Desktop muncul shortcut **LK Monitoring**.

Selanjutnya cukup klik dua kali **LK Monitoring** di Desktop. Aplikasi memperbarui dirinya sendiri setiap dibuka. Bila aplikasi sedang jalan saat admin merilis versi baru, muncul banner biru **Versi baru tersedia**: tekan **Perbarui sekarang**.

## 2. Persiapan pertama

Aplikasi memandu 4 langkah:

1. **Masuk Google.** Unggah `lk-monitoring.json`, lalu pilih akun Google kamu di jendela yang muncul. Bila muncul "Google hasn't verified this app", pilih **Advanced → Go to LK Monitoring (unsafe)**, lalu izinkan. Ini aplikasi internal tim.
2. **Pilih nama petugas.** Nama kamu biasanya sudah terpilih dari daftar akses.
3. **Hubungkan WhatsApp.** Jendela Chrome khusus terbuka. Scan QR pakai HP: WhatsApp → Perangkat tertaut → Tautkan perangkat. Jendela ini **jangan ditutup** selama mengirim.
4. **Batas harian.** Disarankan 40 pesan per hari. Di atas 50 wajib mengetik **risiko ditanggung sendiri**, karena risiko blokir naik.

## 3. Sehari-hari

### Hari ini

- **Kartu Sekarang**: sesi yang berjalan dan tombol **Kirim N pesan**. Pesan dikirim satu per satu dengan jeda acak 45–120 detik, lalu berhenti sendiri saat kuota sesi habis.
- **Bypass sesi** (hanya bila mendesak): link merah di kartu Sekarang saat di luar sesi atau kuota sesi habis. Wajib mengetik "risiko ditanggung sendiri". Jam dan kuota sesi diabaikan, tapi batas harian, jeda, dan jam 07.00–22.00 tetap berlaku. Hanya untuk hari itu.
- Nyalakan **Mode coba** bila ingin melihat prosesnya tanpa benar-benar mengirim.
- Jadwal sesi: 10.00–13.59 (10), 14.00–15.59 (10), 16.00–18.59 (15), 19.00–20.59 (15), 21.00–22.00 (10).
- **Tombol bulat** melayang = hitung mundur sesi. Arahkan kursor untuk melihat menit dan detiknya. Seret untuk memindahkannya; posisinya diingat.
- Angka merah di tombol bulat = **notifikasi** baru. Ketuk untuk melihatnya dan pindah halaman:
  - **Sesi n terlewat**: fasil yang belum dikirimi tetap di antrean dan ikut di sesi berikutnya. Kuota sesi tidak menumpuk, tapi batas harian 40 biasanya masih bisa dikejar.
  - **Lanjutan dari kemarin**, **Minggu baru dimulai**, **Broadcast minggu ini sudah terkirim**.
  - **Fasil perlu dichat lagi**: sudah dihubungi minggu ini tapi isian LK-nya belum lengkap. Tekan **Lihat daftar**, lalu klik fasil untuk membuka LK dan chat-nya di Hari ini.
  - **Fasil di luar Broadcast belum dihubungi**: fasil P1/P2/P3 yang tidak dikirimi Broadcast otomatis. Chat langsung dari panelnya; setelah itu balasannya ikut dicek otomatis.
  - **Fasil menunggu balasan Anda**: fasil sudah membalas dan belum dibalas lagi (dicek tiap 10 menit). Hilang sendiri setelah dibalas, dari aplikasi maupun dari HP.
  - Tekan **Nyalakan notifikasi desktop** di panel notifikasi supaya Windows memberi tahu saat ada fasil baru membalas, selama halaman aplikasi terbuka.
  - **Ada perubahan data baru** di Broadcast atau LK.

### Alur satu minggu

Halaman Hari ini menampilkan **WEEK** yang sedang dipakai dan sesi isian LK hari itu.

- **Senin–Selasa**: Broadcast ke semua fasil di sheet Broadcast (40 per hari), isi LK sesi Senin–Rabu.
- **Rabu–Jumat**: tindak lanjut lewat chat (template Tanya belum submit / progres / reviu), isi LK sesi Rabu–Jumat.
- **Senin berikutnya**: aplikasi otomatis memakai tab **WEEK** terbaru di LK, dan Broadcast dikirim lagi dengan data progres terbaru.

### Panel fasil (klik nama fasil)

- **Di LK**: sekolah binaan, progres, dan prioritas.
  - Pilih **Sesi Senin–Rabu / Rabu–Jumat**, isi **Status komunikasi** sekali untuk semua sekolahnya.
  - Klik sekolah untuk mengisi **ketiga alasan** (progres, submit, reviu) dan tindak lanjut, lalu **Simpan ke LK**. Sekolah yang belum submit terisi otomatis: alasan submit "Progres fisik belum mencapai 50%" (bila progres < 50%) dan alasan reviu "Sekolah Belum Submit". Tanda **✓ Selesai** muncul bila semua sudah terisi.
- **Di WhatsApp**: percakapan dengan fasil.
  - Pakai tombol template (**Tanya belum submit**, **Tanya progres**, **Tanya belum reviu**, **Terima kasih**) lalu **Kirim balasan**.
- **Tahap** di atas panel: Broadcast terkirim → Dibaca → Membalas → Isian ditanyakan → LK lengkap. Bila chat lewat HP, klik tahapnya untuk mencentang sendiri.
- **Kirim ulang broadcast**: pesan yang sudah terkirim minggu ini tidak dikirim lagi walau isi Broadcast berubah. Pakai tombol ini bila memang perlu kirim susulan.

### Rekap

Jumlah sekolah P1/P2/P3/Selesai, kemajuan fasil minggu ini per tab Semua/P1/P2/P3 (dihubungi → membalas → LK lengkap, mulai dari nol tiap Senin), fasil yang tidak masuk Broadcast, dan tabel per fasil (15 per halaman) yang bisa diurutkan dan disaring.

**Tahap chat minggu ini**: papan berisi kolom Belum dihubungi → Sudah dihubungi → Dibaca → Membalas → Isian ditanyakan → LK lengkap. Tiap fasil ada di tahap terjauhnya minggu ini, lengkap dengan kontak terakhir. Klik fasil untuk lanjut chat dan isi LK. Bisa disaring P1/P2/P3 atau Di luar Broadcast.

### Log

- **Per hari**: pilih tanggal di kalender untuk melihat perubahan data Broadcast/LK dan aktivitas fasil hari itu, dikelompokkan per sesi.
- **Riwayat per fasil**: kapan fasil dikirimi Broadcast, membaca, membalas, ditanya lewat aplikasi, dan kapan LK-nya diisi.
- Disimpan 90 hari.

### Tarik Cutoff (khusus admin cutoff)

Pilih jenis tarikan (Harian / Mingguan), WEEK, dan file cutoff → **Cek file** → periksa angkanya → **Tulis ke WEEK n**.

### Bingung?

Ketuk tombol bulat → **Panduan** (aplikasi menunjuk bagian layar satu per satu) atau **Tanya jawab** (sesi terlewat, besok harinya, chat di luar sesi, dan lainnya).

## 4. Tips supaya nomor tidak diblokir

- Jangan menaikkan batas harian di atas 50.
- Biarkan aplikasi yang mengatur jeda. Jangan mengirim massal manual dari HP di waktu yang sama.
- Bila pengiriman berhenti karena 2 kali gagal berturut-turut, cek WhatsApp di jendela Chrome dulu sebelum mulai lagi.

## 5. Kalau ada masalah

| Masalah | Yang dilakukan |
|---|---|
| Pengingat merah "WhatsApp belum dibuka" | Tekan **Buka WhatsApp**, scan QR bila diminta. |
| Pengingat kuning "Server perlu dijalankan ulang" | Klik dua kali **stop.bat** di folder aplikasi, lalu buka lagi **LK Monitoring**. |
| Aplikasi tidak terbuka | Klik dua kali **stop.bat**, lalu buka lagi. Bila masih gagal, kirim file `%APPDATA%\LKMonitoring\logs\server.log` ke admin. |
| Ganti akun Google | Klik profil di kiri bawah → **Keluar / ganti akun Google**. |
| Mematikan aplikasi | Klik dua kali **stop.bat** di `%LOCALAPPDATA%\LKMonitoring\app`. Aplikasi juga mati sendiri saat laptop dimatikan. |

Data kamu (login, riwayat kirim, sesi WhatsApp) tersimpan di `%APPDATA%\LKMonitoring` dan tidak ikut terhapus saat aplikasi diperbarui atau cache browser dihapus. Jangan hapus folder itu di tengah minggu: aplikasi akan lupa siapa yang sudah dikirimi, sehingga Broadcast bisa terkirim dua kali.
