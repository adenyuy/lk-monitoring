(()=>{"use strict";(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,73268,a=>{let n=["Min","Sen","Sel","Rab","Kam","Jum","Sab"];a.s(["E",0,n,"t",0,{perlu_telepon:{label:"Perlu ditelepon",tone:"bad"},dibaca:{label:"Dibaca, belum membalas",tone:"warn"},terkirim:{label:"Terkirim, belum dibaca",tone:"info"},menunggu:{label:"Membalas, belum tuntas",tone:"info"},belum:{label:"Belum dihubungi",tone:"muted"},terhubung:{label:"Terhubung",tone:"ok"},beres:{label:"Semua hijau",tone:"ok"}},"K",0,{T:{bg:"#e3f3ea",fg:"#1e5e3c",label:"Respon baik"},TP:{bg:"#d8efe9",fg:"#155e52",label:"Ditelepon"},T1:{bg:"#fff4de",fg:"#7a4900",label:"Membalas, belum konfirmasi"},T2:{bg:"#fde9d2",fg:"#8a4a0c",label:"Membalas lambat"},R:{bg:"#e8edf9",fg:"#2346a0",label:"Dibaca, tidak membalas"},C:{bg:"#fcecec",fg:"#a6282b",label:"Centang satu"},C2:{bg:"#f3eef0",fg:"#7a3b45",label:"Centang dua, tidak membalas"},N:{bg:"#f2e6ee",fg:"#8a2d63",label:"Tidak ada WA"}},"u",0,{pendahuluan:"Pendahuluan",berkala:"Laporan berkala",l50:"Laporan 50%",l100:"Laporan 100%",selesai:"Semua hijau"},"$",0,function(a){let e=new Date(`${a}T00:00:00`);return`${n[e.getDay()]} ${e.getDate()}`},"D",0,function(a){let n=a.replace(/^(dr|ir|prof|drs|hj|h)\.?\s+/gi,"").replace(/[.,]/g," ").split(/\s+/).filter(a=>/^[A-Za-z]/.test(a)&&a.length>1);return((n[0]?.[0]??"?")+(n[1]?.[0]??"")).toUpperCase()}])},18287,a=>{let n="{salam}";function e(a=new Date){let n=a.getHours();return n<11?"Selamat pagi":n<15?"Selamat siang":n<18?"Selamat sore":"Selamat malam"}let i="Terima kasih atas perhatian dan kerja samanya 🙏",t="https://revitsd.kemendikdasmen.go.id/rolelogin",l="📌 *INFORMASI & PENGINGAT RESMI | TIM MONITORING*\nSubdit Sarpras – Direktorat SD, Kemendikdasmen",s=`🔗 *Akses Aplikasi Revitalisasi SD:*
${t}

Apabila terdapat kendala teknis di lapangan, mohon segera dikoordinasikan dengan Tim Monitoring.

Terima kasih atas perhatian, pendampingan, dan kerja samanya. 🙏🏻

Salam,
Tim Monitoring`;function u(a,n){let e=a.detail&&!/^(Belum|Sudah)$/.test(a.detail)?` (${a.detail})`:"",i="fasil"===a.pelaku&&n?" — oleh Bapak/Ibu":"";return`• ${a.judul}${e}${i}`}function r(a){return(a.sekolah??[]).filter(a=>a.todo.length).slice().sort((a,n)=>a.nama.localeCompare(n.nama))}function o(a){return r(a).map(a=>({nama:a.nama,todo:a.todo.filter(a=>"fasil"===a.pelaku)})).filter(a=>a.todo.length).map((a,n)=>`${n+1}. *${a.nama}*
${a.todo.map(a=>`   ${u(a,!1)}`).join("\n")}`).join("\n\n")}function k(a,n,e=""){let i=a.kab?` - ${a.kab}`:"",t=a.angkatan?` | Angkatan ${a.angkatan}`:"";return`${n+1}. ${a.nama}${a.npsn?` (NPSN: ${a.npsn})`:""}${i}${t}${e}`}function d(a,n,e){return r(a).map(a=>({x:a,t:a.todo.find(n)})).filter(a=>a.t).map(({x:a,t:n},i)=>k(a,i,e&&n?e(n):"")).join("\n")}let m=a=>"lp"===a.kode,p=a=>"lp_rev"===a.kode&&/revisi/i.test(a.detail),g=a=>"lp_rev"===a.kode&&!/revisi/i.test(a.detail),h=a=>null!=a.tunggu?` | Waktu tunggu reviu: ${Math.round(a.tunggu)} hari`:"";function b(a){return(a.fasil??[]).filter(a=>a.sulit).map((a,n)=>`${n+1}. ${a.nama} (${a.sekolah} sekolah dampingan)`).join("\n")}function f(a){return(a.fasil??[]).filter(a=>a.perlu).map((a,n)=>{let e=a.todo_fasil?`, ${a.todo_fasil} laporan menunggu reviu fasil`:"";return`${n+1}. ${a.nama}: ${a.perlu} dari ${a.sekolah} sekolah masih perlu melengkapi laporan${e}`}).join("\n")}let $=/^\s*(\d{1,3})\s*[.)]\s*(.*)$/,c=/^\s*[•*\-]?\s*\*?kendala\*?\s*[:：=-]\s*(.*)$/i,y=/^\s*[•*\-]?\s*\*?(?:tindak\s*lanjut|tl|rencana(?:\s*tindak\s*lanjut)?)\*?\s*[:：=-]\s*(.*)$/i,j=/^\s*[•\-]\s*(.+)$/;function v(a){return a.replace(/\*/g,"").replace(/^\.{2,}$/,"").replace(/\s*\.{3,}\s*$/,"").trim()}function _(a){return a.toLowerCase().replace(/[^a-z0-9]+/g," ").trim()}a.s(["g",0,n,"c",0,{fasil:[{kode:"{salam}",arti:"Selamat pagi/siang/sore/malam (otomatis saat dikirim)"},{kode:"{nama}",arti:"Nama fasil"},{kode:"{jumlah_sekolah}",arti:"Jumlah sekolah yang masih punya to-do"},{kode:"{daftar_tanya}",arti:"Daftar sekolah + to-do + baris Kendala/Tindak lanjut"},{kode:"{daftar_todo}",arti:"Daftar sekolah + to-do (tanpa isian)"},{kode:"{daftar_reviu}",arti:"Laporan yang menunggu reviu fasil"},{kode:"{daftar_sekolah}",arti:"Sekolah yang punya to-do: nama (NPSN) - kab/kota | angkatan"},{kode:"{sekolah_lp_belum}",arti:"Sekolah yang belum submit Lap. Pendahuluan (NPSN, kab/kota, angkatan)"},{kode:"{sekolah_lp_revisi}",arti:"Sekolah yang Lap. Pendahuluannya berstatus Revisi"},{kode:"{sekolah_lp_reviu}",arti:"Sekolah yang Lap. Pendahuluannya menunggu reviu fasil, dengan waktu tunggu"},{kode:"{petugas}",arti:"Nama Anda"}],koor:[{kode:"{salam}",arti:"Salam sesuai jam"},{kode:"{nama}",arti:"Nama koordinator"},{kode:"{daftar_sulit}",arti:"Fasil yang sulit dihubungi"},{kode:"{daftar_fasil}",arti:"Rekap to-do per fasil binaan"},{kode:"{petugas}",arti:"Nama Anda"}],sekolah:[{kode:"{salam}",arti:"Salam sesuai jam"},{kode:"{nama}",arti:"Nama kepala sekolah"},{kode:"{sekolah}",arti:"Nama sekolah"},{kode:"{daftar_todo}",arti:"Laporan yang perlu dilengkapi sekolah"},{kode:"{petugas}",arti:"Nama Anda"}]},"s",0,function(a){let n=[],e=null,i=null,t=null;for(let l of a.replace(/\r/g,"").split("\n")){let a=$.exec(l);if(a&&!c.test(a[2])&&!y.test(a[2])){e={no:Number(a[1]),judul:v(a[2]),kendala:"",tl:"",poin:[]},n.push(e),i=null,t=null;continue}if(!e)continue;let s=c.exec(l),u=y.exec(l),r=i??e;if(s){r.kendala=v(s[1]),t="kendala";continue}if(u){r.tl=v(u[1]),t="tl";continue}let o=j.exec(l);if(o){i={judul:v(o[1]),kendala:"",tl:""},e.poin.push(i),t=null;continue}let k=v(l);if(!l.trim()){t=null;continue}t&&k&&(r[t]=`${r[t]} ${k}`.trim())}for(let a of n)a.poin=a.poin.filter(a=>a.kendala||a.tl);return n.filter(a=>a.kendala||a.tl||a.poin.length)},"H",0,function(a,n){let e=new Map;for(let i of a){let a=_(i.judul),t=(a?n.find(n=>{let e=_(n.nama);return e&&(a.includes(e)||e.includes(a))}):void 0)??n[i.no-1];t&&!e.has(t)&&e.set(t,i)}return e},"D",0,function(a,i,t,l=!0){let s=r(i),$=a;for(let[a,n]of Object.entries({"{nama}":()=>(i.kepsek||i.nama).trim(),"{petugas}":()=>t,"{jumlah_sekolah}":()=>String(s.length),"{daftar_tanya}":()=>r(i).map((a,n)=>`${n+1}. *${a.nama}*
${a.todo.map(a=>`   ${u(a,!0)}
   Kendala: ...
   Tindak lanjut: ...`).join("\n")}`).join("\n\n"),"{daftar_todo}":()=>i.todo?i.todo.map(a=>u(a,!1)).join("\n"):r(i).map((a,n)=>`${n+1}. *${a.nama}*
${a.todo.map(a=>`   ${u(a,!0)}`).join("\n")}`).join("\n\n"),"{daftar_reviu}":()=>o(i),"{daftar_sekolah}":()=>s.map((a,n)=>k(a,n)).join("\n"),"{sekolah_lp_belum}":()=>d(i,m),"{sekolah_lp_revisi}":()=>d(i,p),"{sekolah_lp_reviu}":()=>d(i,g,h),"{daftar_sulit}":()=>b(i),"{daftar_fasil}":()=>f(i),"{sekolah}":()=>i.nama}))$.includes(a)&&($=$.split(a).join(n()));return l||($=$.split(n).join(e())),$},"t",0,function(a,n,e){var i,t;let l=a.split(/\s+/).filter(Boolean).join(" "),s=n.trim();if(!l)return{kendala:"",tl:s};let u=function(a,n){let e=_(a);if(!e)return"";let i=n.find(a=>_(a)===e||_(a.replace(/^\d+\.\s*/,""))===e);if(i)return i;let t=/^(\d{1,2})\s*[.)]?$/.exec(a.trim())??/^(\d{1,2})\s*[.)]\s/.exec(a.trim());if(t){let a=n.find(a=>a.startsWith(`${t[1]}.`));if(a)return a}if(/^(tidak ada|tdk ada|ga ada|gak ada|tidak ada kendala|aman|lancar|ok|nihil|belum ada|-)$/.test(e))return n.find(a=>_(a).includes("tidak ada kendala"))??"";if(/^lainnya\b/.test(e))return n.find(a=>/lainnya/i.test(a))??"";let l="",s=0,u=new Set(e.split(" ").filter(a=>a.length>3));for(let a of n){let n=_(a.replace(/^\d+\.\s*/,"")).split(" ").filter(a=>a.length>3);if(!n.length)continue;let e=n.filter(a=>u.has(a)).length/n.length;e>s&&(s=e,l=a)}return s>=.6?l:""}(l,e);if(u)return{kendala:u,tl:s};let r=e.find(a=>/lainnya/i.test(a));return r?{kendala:r,tl:(i=l,(t=s)?_(t).startsWith(_(i))?t:`${i.replace(/[\s,.;]+$/,"")}, ${t}`:i)}:{kendala:l,tl:s}},"d",0,function(a,n,e){let i=_(n),t=i?a.poin.find(a=>{let n=_(a.judul);return n.startsWith(i)||n.length>8&&i.startsWith(n)}):void 0;return t||(a.kendala||a.tl?{kendala:a.kendala,tl:a.tl}:1===a.poin.length&&1===e?a.poin[0]:null)},"v",0,function(a,n){return Object.entries({"{daftar_tanya}":()=>!r(n).length,"{daftar_todo}":()=>n.todo?!n.todo.length:!r(n).length,"{daftar_reviu}":()=>!o(n),"{daftar_sekolah}":()=>!r(n).length,"{sekolah_lp_belum}":()=>!d(n,m),"{sekolah_lp_revisi}":()=>!d(n,p),"{sekolah_lp_reviu}":()=>!d(n,g),"{daftar_sulit}":()=>!b(n),"{daftar_fasil}":()=>!f(n)}).filter(([n,e])=>a.includes(n)&&e()).map(([a])=>a)},"e",0,function(a,n){if(!n.length)return a;let e=a=>n.reduce((n,e)=>n+(a?.[e]??0),0),i=e(a.posisi);if(!i)return null;let t=a=>n.includes(a.posisi??"");return{...a,perlu:i,sekolah:a.sekolah?.map(a=>({...a,todo:a.todo.filter(t)})).filter(a=>a.todo.length),todo:a.todo?.filter(t),fasil:a.fasil?.filter(a=>e(a.posisi)).map(a=>({...a,perlu:e(a.posisi)}))}},"b",0,e,"w",0,function(a){return"fasil"===a?[{kode:"tanya",judul:"Tanya kendala per sekolah",bawaan:!0,ket:"Semua sekolah sekaligus, format Kendala / Tindak lanjut. Balasannya bisa langsung dibaca aplikasi.",teks:`${n} Bapak/Ibu {nama}, izin menindaklanjuti progres pelaporan sekolah dampingan Bapak/Ibu.

Berikut laporan yang masih perlu dilengkapi:

{daftar_tanya}

Mohon dibantu mengisi *Kendala* dan *Tindak lanjut* untuk tiap sekolah (cukup isi titik-titiknya), supaya mudah kami rekap. ${i}`},{kode:"ingat",judul:"Pengingat to-do",bawaan:!0,ket:"Daftar yang perlu dilengkapi tanpa meminta jawaban per sekolah.",teks:`${n} Bapak/Ibu {nama}, izin mengingatkan laporan sekolah dampingan yang masih perlu dilengkapi di aplikasi:

{daftar_todo}

Mohon dibantu mendampingi sekolah agar laporannya segera lengkap. ${i}`},{kode:"reviu",judul:"Ingatkan reviu",bawaan:!0,ket:"Hanya laporan yang sudah masuk dan menunggu reviu fasil.",teks:`${n} Bapak/Ibu {nama}, izin menginformasikan laporan sekolah dampingan berikut sudah masuk dan menunggu reviu Bapak/Ibu:

{daftar_reviu}

Mohon dibantu segera direviu di aplikasi. ${i}`},{kode:"tagih",judul:"Tagih informasi",bawaan:!0,ket:"Untuk fasil yang belum menjawab pertanyaan sebelumnya.",teks:`${n} Bapak/Ibu {nama}, mohon izin menindaklanjuti permintaan informasi yang sudah kami sampaikan sebelumnya.

Mohon kesediaan Bapak/Ibu untuk *segera* mengirimkan informasi tersebut *menggunakan format yang sudah kami kirimkan* (cukup disalin, lalu diisi per sekolah), agar data dapat kami rekap dengan tepat.

${i}`},{kode:"format",judul:"Minta sesuai format",bawaan:!0,ket:"Balasan fasil belum mengikuti format per sekolah.",teks:`Terima kasih atas informasinya, Bapak/Ibu {nama} 🙏

Mohon izin, agar data dapat kami rekap dengan tepat, mohon informasi tersebut *dikirim ulang sesuai format* berikut (diisi per sekolah):

{daftar_tanya}`},{kode:"bc_lp_belum",judul:"BC LP belum submit",bawaan:!0,ket:"Broadcast resmi: daftar sekolah yang belum submit Laporan Pendahuluan (NPSN, kab/kota, angkatan).",teks:`${l}

{salam}, Bapak/Ibu {nama}. 🙏🏻

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Berdasarkan hasil pemantauan pada sistem Aplikasi Revitalisasi SD, sekolah dampingan Bapak/Ibu dari seluruh angkatan yang telah menyelesaikan penandatanganan PKS berikut tercatat belum melakukan submit Laporan Pendahuluan:

🏫 *Daftar Sekolah Binaan:*
{sekolah_lp_belum}

Mengingat Laporan Pendahuluan merupakan persyaratan administrasi penting untuk kelanjutan pelaksanaan dan tahapan berikutnya, mohon bantuan Bapak/Ibu Fasilitator untuk segera:
1. Mengingatkan dan mendampingi sekolah dalam menyusun berkas Laporan Pendahuluan.
2. Memastikan sekolah mengunggah dokumen dan menekan tombol Submit pada Aplikasi Revitalisasi SD.
3. Melakukan verifikasi terhadap dokumen yang telah diunggah oleh sekolah.

${s}`},{kode:"bc_lp_revisi",judul:"BC LP perlu revisi",bawaan:!0,ket:"Broadcast resmi: sekolah yang sudah submit Laporan Pendahuluan tapi hasil reviunya Revisi.",teks:`${l}

{salam}, Bapak/Ibu {nama}. 🙏🏻

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Berdasarkan pemantauan pada Aplikasi Revitalisasi SD, sekolah dampingan Bapak/Ibu dari seluruh angkatan berikut sudah melakukan submit Laporan Pendahuluan, tetapi hasil reviunya masih berstatus *Revisi*:

🏫 *Daftar Sekolah yang Perlu Revisi:*
{sekolah_lp_revisi}

Mohon bantuan Bapak/Ibu Fasilitator untuk:
1. Meninjau kembali catatan hasil reviu Laporan Pendahuluan dan menyampaikan perbaikan yang diperlukan kepada sekolah dampingan.
2. Mendampingi sekolah agar memperbaiki atau melengkapi dokumen sesuai catatan, kemudian mengunggah dan melakukan submit ulang Laporan Pendahuluan.
3. Memastikan dokumen hasil perbaikan ditindaklanjuti dan diperiksa kembali sesuai alur reviu pada aplikasi.

${s.replace("kendala teknis di lapangan, mohon segera dikoordinasikan dengan","kendala teknis atau administrasi, mohon segera berkoordinasi dengan")}`},{kode:"bc_lp_reviu",judul:"BC LP menunggu reviu",bawaan:!0,ket:"Broadcast resmi: sekolah yang sudah submit Laporan Pendahuluan tapi belum direviu fasil, dengan waktu tunggu.",teks:`${l}

{salam}, Bapak/Ibu {nama}. 🙏🏻

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Berdasarkan hasil pemantauan pada Aplikasi Revitalisasi SD, sekolah dampingan Bapak/Ibu dari seluruh angkatan berikut telah melakukan submit Laporan Pendahuluan, namun status reviu Fasilitator masih tercatat *Belum*:

🏫 *Daftar Sekolah Menunggu Reviu:*
{sekolah_lp_reviu}

Mohon bantuan Bapak/Ibu Fasilitator untuk segera:
1. Memeriksa dan mereviu Laporan Pendahuluan yang telah disubmit oleh masing-masing sekolah dampingan.
2. Memberikan hasil reviu melalui aplikasi. Apabila diperlukan perbaikan dokumen, mohon cantumkan catatan revisi yang jelas agar sekolah dapat segera menindaklanjuti.
3. Memastikan hasil dan status reviu tercatat pada aplikasi serta mengoordinasikan tindak lanjut dengan sekolah terkait.

${s.replace("kendala teknis di lapangan, mohon segera dikoordinasikan dengan","kendala teknis dalam proses reviu, mohon segera berkoordinasi dengan")}`},{kode:"info",judul:"Info / pengumuman",bawaan:!0,ket:"Pesan bebas, mis. undangan grup atau link survei. Ganti isinya sesuai kebutuhan.",teks:`${n} Bapak/Ibu {nama},

[tulis informasinya di sini]

${i}`},{kode:"makasih",judul:"Terima kasih",bawaan:!0,ket:"Menutup percakapan setelah fasil menjawab.",teks:"Terima kasih atas informasinya, Bapak/Ibu {nama}. Sudah kami catat. Mohon terus dampingi sekolah binaan agar laporannya segera lengkap 🙏"}]:"koor"===a?[{kode:"bc_koor_lp",judul:"BC Koordinator: Laporan Pendahuluan",bawaan:!0,ket:"Broadcast resmi ke Koordinator PTN tentang pendampingan dan verifikasi Laporan Pendahuluan.",teks:`📌 *INFORMASI RESMI | TIM MONITORING*
Subdit Sarpras – Direktorat SD, Kemendikdasmen

{salam},
Yth. Bapak/Ibu {nama} selaku Koordinator PTN.

Perkenalkan, saya {petugas} dari Tim Monitoring Direktorat SD.

Mohon izin menyampaikan informasi terkait pendampingan penyusunan dan verifikasi Laporan Pendahuluan pada Aplikasi Revitalisasi SD:

1. 📄 *Kewajiban Laporan Pendahuluan:* Sekolah penerima bantuan diwajibkan menyusun dan mengunggah Laporan Pendahuluan (termasuk foto kondisi 0% dan jadwal pelaksanaan) sebagai syarat mutlak sebelum pekerjaan fisik dilanjutkan.

2. 🤝 *Pendampingan & Verifikasi:* Mohon bantuan Bapak/Ibu Koordinator untuk mengarahkan rekan-rekan Fasilitator agar memastikan sekolah dampingannya segera mengunggah dokumen serta melakukan verifikasi secara berkala di aplikasi.

3. 🔗 *Akses Sistem:* Pemantauan dan progres pelaporan dapat dipantau langsung melalui Aplikasi Revitalisasi SD pada tautan:
${t}

Mohon kerja sama Bapak/Ibu untuk bersama-sama memantau dan mendampingi ketepatan waktu pelaporan di wilayah masing-masing.

Terima kasih atas perhatian dan kerja samanya. 🙏🏻

Salam,
Tim Monitoring`},{kode:"rekap",judul:"Rekap to-do fasil binaan",bawaan:!0,ket:"Ringkasan per fasil: berapa sekolah yang laporannya belum lengkap.",teks:`${n} Bapak/Ibu {nama}, izin menyampaikan rekap progres pelaporan sekolah dampingan fasilitator binaan Bapak/Ibu:

{daftar_fasil}

Mohon bantuan Bapak/Ibu untuk mendorong fasilitator agar laporan sekolah segera lengkap. ${i}`},{kode:"sulit",judul:"Fasil sulit dihubungi",bawaan:!0,ket:"Koordinator yang fasilnya hanya membaca chat, centang satu, atau tidak ada WA (dari WhatsApp minggu ini & Log Komunikasi).",teks:`${n} Bapak/Ibu {nama}, mohon izin. Kami dari tim monitoring ingin menyampaikan bahwa fasilitator berikut belum dapat kami hubungi untuk konfirmasi progres pelaporan sekolah dampingan:

{daftar_sulit}

Mohon bantuan Bapak/Ibu untuk mengingatkan fasilitator tersebut agar dapat merespons pesan kami. ${i}`},{kode:"info",judul:"Info / pengumuman",bawaan:!0,ket:"Pesan bebas untuk koordinator.",teks:`${n} Bapak/Ibu {nama},

[tulis informasinya di sini]

${i}`}]:[{kode:"ingat",judul:"Pengingat laporan sekolah",bawaan:!0,ket:"Ke kepala sekolah: laporan yang perlu dikirim/diunggah sekolah (tanpa tugas reviu fasil).",teks:`${n} Bapak/Ibu {nama}, Kepala {sekolah}. Kami dari tim monitoring Revitalisasi SD 2026 ingin mengingatkan laporan yang masih perlu dilengkapi di aplikasi:

{daftar_todo}

Bila ada kendala, mohon dapat disampaikan melalui balasan pesan ini. ${i}`},{kode:"info",judul:"Info / pengumuman",bawaan:!0,ket:"Pesan bebas untuk kepala sekolah.",teks:`${n} Bapak/Ibu {nama}, Kepala {sekolah}.

[tulis informasinya di sini]

${i}`}]},"R",0,function(a,n=e()){let t=a.koor?`Bapak/Ibu ${a.koor}`:"Bapak/Ibu Koordinator",l=a.sekolah_detail.filter(a=>a.todo.length).slice().sort((a,n)=>a.nama.localeCompare(n.nama)),s=l.slice(0,15).map((a,n)=>`${n+1}. *${a.nama}*: ${a.todo.map(a=>a.judul).join(", ")}`).join("\n")+(l.length>15?`
… dan ${l.length-15} sekolah lainnya`:""),u=a.sekolah_detail.flatMap(a=>a.todo.filter(a=>"fasil"===a.pelaku).map(n=>`• ${a.nama}: ${n.judul}`)),r=`fasilitator *${a.nama}*${a.ptn?` (${a.ptn})`:""}`,o=[{kode:"sulit",judul:"Fasil tidak membalas",bawaan:!0,ket:"Chat ke fasil hanya dibaca, tidak sampai, atau tidak dibalas.",teks:`${n} ${t}, mohon izin. Kami dari tim monitoring Revitalisasi SD 2026 ingin meminta bantuan terkait ${r}. Sudah beberapa kali kami hubungi, namun belum mendapat respons.

${l.length?`Sekolah dampingan beliau yang laporannya masih perlu dilengkapi:

${s}

`:""}Mohon bantuan ${t} untuk mengingatkan beliau agar dapat membalas pesan kami. ${i}`}];return l.length&&o.push({kode:"macet",judul:"Laporan tidak bergerak",bawaan:!0,ket:"Fasil merespons, tapi laporan sekolahnya belum bertambah.",teks:`${n} ${t}, mohon izin. Kami ingin menyampaikan bahwa ${r} sudah merespons pesan kami, namun laporan sekolah dampingannya belum bertambah sejak cutoff sebelumnya:

${s}

Mohon bantuan ${t} untuk mendorong agar laporan tersebut segera dilengkapi. ${i}`}),u.length&&o.push({kode:"reviu",judul:"Reviu menunggu fasil",bawaan:!0,ket:"Laporan sekolah sudah masuk, tapi belum direviu fasil.",teks:`${n} ${t}, mohon izin. Laporan sekolah dampingan ${r} sudah masuk dan menunggu reviu:

${u.slice(0,15).join("\n")}${u.length>15?`
… dan ${u.length-15} lainnya`:""}

Mohon bantuan ${t} untuk mengingatkan beliau agar segera mereviu. ${i}`}),o.push({kode:"info",judul:"Pesan bebas",bawaan:!0,ket:"Tulis sendiri pesannya.",teks:`${n} ${t}, mohon izin. Terkait ${r}:

[tulis pesannya di sini]

${i}`}),o},"x",0,function(a,n,t=e()){let l=a.kepsek?`Bapak/Ibu ${a.kepsek}`:"Bapak/Ibu Kepala Sekolah",s=`*${a.nama}*`,u=a.todo.filter(a=>"fasil"!==a.pelaku),r=n?` Hal ini juga sudah kami koordinasikan dengan fasilitator sekolah, *${n}*.`:"",o=[];return u.length&&o.push({kode:"todo_sekolah",judul:"Pengingat laporan sekolah",bawaan:!0,ket:"Laporan yang masih perlu dikirim / diunggah oleh sekolah.",teks:`${t} ${l}, Kepala ${s}. Kami dari tim monitoring Revitalisasi SD 2026 izin mengingatkan, berdasarkan data kami laporan berikut masih perlu dilengkapi oleh sekolah:

${u.map((a,n)=>`${n+1}. ${a.judul}`).join("\n")}

Mohon bantuan ${l} agar laporan tersebut dapat segera dilengkapi.${r} ${i}`}),o.push({kode:"info_sekolah",judul:"Info / pengumuman",bawaan:!0,ket:"Teks bebas: ganti bagian dalam kurung siku.",teks:`${t} ${l}, Kepala ${s}. Kami dari tim monitoring Revitalisasi SD 2026 izin menyampaikan informasi:

[tulis informasinya di sini]
${r?`
${r.trim()}`:""}
${i}`}),o}])}])})();