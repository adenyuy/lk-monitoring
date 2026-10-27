# Uji sebelum rilis ke tim

Centang satu per satu. Uji yang mengirim pesan **hanya ke nomormu sendiri** atau dengan **Mode coba**.

## A. Rilis pertama (laptop admin)

- [ ] `git push origin main`, lalu `git checkout stable && git merge main && git push && git checkout main`.
- [ ] GitHub → **Actions** → workflow **Rilis** hijau. Bila gagal di langkah push: Settings → Actions → General → Workflow permissions → **Read and write**.
- [ ] Branch `release` muncul di GitHub dan berisi `start.bat`, `backend/`, dan `web/out/`.

## B. Pasang di laptop bersih (atau akun Windows baru)

- [ ] Salin `install.bat` ke laptop itu, klik dua kali. Catat lamanya: target kurang dari 15 menit.
- [ ] Git, Python 3.12, dan Chrome terpasang otomatis bila belum ada.
- [ ] Shortcut **LK Monitoring** muncul di Desktop, dan browser terbuka ke aplikasi.
- [ ] Persiapan 4 langkah berhasil: unggah `lk-monitoring.json`, login Google, pilih nama, scan QR, batas harian.
- [ ] Coba batas 55: tombol simpan baru aktif setelah mengetik "risiko ditanggung sendiri". Kembalikan ke 40.
- [ ] Tutup browser lalu klik shortcut lagi: aplikasi langsung terbuka tanpa jendela hitam.
- [ ] `stop.bat` mematikan aplikasi, dan shortcut menyalakannya lagi.

## C. Pembaruan otomatis

- [ ] Ubah sesuatu yang kecil di `main`, merge ke `stable`, lalu push. Tunggu Actions hijau.
- [ ] Di laptop uji, buka **Rekap** atau **Hari ini**. Banner biru **Versi baru tersedia** muncul paling lama 30 menit kemudian (atau segera setelah halaman dimuat ulang).
- [ ] Tekan **Perbarui sekarang**: aplikasi mulai ulang, halaman memuat ulang sendiri, dan nomor versi di kaki halaman berubah.
- [ ] Tekan **Buka WhatsApp** lagi. Tidak perlu scan QR ulang.

## D. Fitur yang menulis ke data asli

- [ ] **Kirim Broadcast**: Mode coba 3 fasil, lalu kirim sungguhan ke nomormu sendiri (baris uji di Broadcast).
- [ ] **Warna Broadcast P1**: baris nomormu berubah kuning atau hijau. Nomor yang tidak terdaftar di WhatsApp jadi merah.
- [ ] **Balas chat dari aplikasi** ke nomormu: pesan masuk di HP, lalu balas dari HP. Dalam 15 menit tahap "Fasil membalas" tercentang dan muncul di Log → Riwayat per fasil.
- [ ] **Isi LK** untuk satu sekolah uji: sel di kolom I dan P–U/V–AA berubah di sheet, dan tercatat di Log.
- [ ] **Fasil di luar Broadcast**: chat dari panelnya. Fasil itu hilang dari notifikasi "belum dihubungi" dan dihitung "Dihubungi" di Rekap.
- [ ] **Tarik Cutoff** ke salinan LK (bukan LK asli): angka sama dengan `tarik.py`.
- [ ] **Pindah WEEK**: setelah tab WEEK baru dibuat di LK, label di Hari ini berganti dalam 5 menit dan tercatat di Log.

## E. Tim

- [ ] Email tiap petugas ada di **sheet Akses** (kolom email, nama petugas, fitur).
- [ ] Sheet Akses dibagikan (minimal Viewer) ke email tim atau lewat link. Sheet Broadcast dan LK boleh tetap lewat link: ID-nya tidak ada di repo.
- [ ] Kirim ke tiap petugas lewat jalur pribadi: `install.bat`, `lk-monitoring.json`, dan `CARA_PAKAI.md`.
- [ ] Pilot 1–2 petugas selama 2 hari sebelum seluruh tim.
