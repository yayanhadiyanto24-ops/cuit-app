# CUIT Smart Architecture — Audit Awal

Tanggal audit: 2026-11-14  
Branch: `cuit-smart-architecture-audit`  
File yang diperiksa: `index.html` pada branch `main`  
Blob SHA saat audit: `ff369cfd6ab3d18c937e38e7a85fc11aeef47cea`

## Status dan batas audit

Audit ini memeriksa kode frontend yang tersedia di `index.html`. Ini belum merupakan audit database Supabase menyeluruh: definisi tabel, trigger, RLS, RPC, indeks, Edge Functions, dan konfigurasi Realtime perlu diperiksa terpisah sebelum migrasi atau perubahan backend dilakukan.

Tidak ada data anggota, saldo, transaksi, atau fungsi produksi yang diubah dalam audit ini.

## Temuan terverifikasi

### 1. Frontend masih terkonsentrasi di satu file besar
- `index.html` berisi 8.267 baris dan sekitar 433.979 byte.
- HTML, CSS, JavaScript, game, feed, ranking, misi, dan integrasi backend bercampur dalam satu dokumen.
- Dampak: perubahan lebih sulit diisolasi dan pengujian regresi lebih sulit dilakukan.

### 2. Feed mengambil seluruh baris curhatan tanpa pagination
- Sekitar baris 4335–4340: query `curhat` melakukan `.select('*')` dan mengurutkan berdasarkan `created_at`, tanpa `.range()` atau batas halaman.
- Sekitar baris 4344 dan seterusnya: pada pemuatan non-feed-only, profil juga diambil secara luas.
- Sekitar baris 4380–4410: sepuluh kategori ranking dipanggil paralel dengan batas 100.
- Dampak potensial: ukuran respons, waktu parsing, memori, dan render meningkat seiring pertumbuhan data.
- Rekomendasi: tentukan strategi pagination/keyset, pilih kolom eksplisit, dan pisahkan query ringkasan dari query feed. Jangan mengubah urutan/aturan feed sebelum perilaku yang diharapkan diuji.

### 3. Realtime memicu refresh data dalam cakupan luas
- Sekitar baris 5175–5215: satu channel berlangganan perubahan pada `curhat`, `comments`, `follows`, profil milik pengguna, dan `cuit_central_entries` milik pengguna.
- Perubahan komentar/follow memanggil `schedulePublicSocialRefresh()`, yang kemudian menjalankan `loadPosts({feedOnly:true})` dan `loadFollows()`.
- Perubahan `curhat` juga memuat ulang feed.
- Dampak potensial: aktivitas sosial yang sering dapat menghasilkan query feed berulang walaupun perubahan hanya relevan untuk satu kartu atau satu komentar.
- Rekomendasi: petakan kebutuhan UI per event; gunakan pembaruan lokal untuk perubahan yang dapat diidentifikasi, dan refresh terarah hanya untuk data yang tidak bisa dihitung aman di klien.

### 4. Ada penundaan pemuatan feed tambahan sebesar 900 ms
- Sekitar baris 8100–8155: wrapper `CUIT REALTIME LOAD CONTROLLER` menunda setiap pemanggilan `loadPosts` selama 900 ms untuk debounce.
- Wrapper juga menggabungkan panggilan, tetapi dapat membuat pemuatan awal dan interaksi yang menunggu `loadPosts` terasa tertunda.
- Rekomendasi: ukur pemanggilan dan kebutuhan debounce; gunakan penjadwalan berbeda untuk initial load dan refresh realtime. Jangan menghapus wrapper sebelum semua pemanggil dan kontrak Promise diuji.

### 5. Kebijakan anti-cache terlalu luas
- Bagian head memakai meta `Cache-Control: no-cache, no-store, must-revalidate`, `Pragma: no-cache`, dan `Expires: 0`.
- Meta cache bukan pengganti konfigurasi cache header server/CDN. `no-store` dapat mengurangi manfaat cache dokumen, sementara aset statis sebaiknya memiliki strategi cache/versioning yang tepat.
- Rekomendasi: tinjau strategi cache hosting dan versioning aset. Jangan mengubahnya tanpa memastikan mekanisme update aplikasi dan service worker (jika kelak ada).

### 6. Realtime channel memiliki sebagian perlindungan lifecycle
- `initGlobalRealtime()` menghapus channel lama sebelum membuat channel baru.
- Ada timer debounce untuk event feed, sosial, dan refresh profil.
- Callback status mencatat `CHANNEL_ERROR` dan `TIMED_OUT` ke console, tetapi belum tampak pusat diagnosis persisten yang menyatukan error, request ID, modul, dan hasil operasi.
- Rekomendasi: tambahkan observabilitas terstruktur dan pemeriksaan reconnect/lifecycle sebelum memperluas langganan.

### 7. Validasi misi Roulette memiliki polling cadangan
- Sekitar baris 7890–7980: validasi misi memanggil RPC `cuit_roulette_claim_mission`, dengan pemeriksaan otomatis berulang sekitar setiap 1.400 ms.
- Ada jalur validasi langsung melalui `validateCuitRouletteMissionAction` dan `checkCuitRouletteMissionNow`.
- Rekomendasi: audit seluruh pemanggil callback like/comment dan definisi RPC sebelum mengubah validasi. Pertahankan polling sebagai fallback sampai event langsung terbukti andal.

### 8. Reload eksplisit masih ada pada beberapa alur
- Tombol refresh manual di sekitar baris 788.
- `location.reload()` muncul pada alur keluar akun dan pendaftaran sekitar baris 6898 dan 7002.
- Reload pada alur autentikasi dapat saja disengaja; jangan disamakan dengan reload saat scroll. Audit pemanggil navigasi dan pemuatan ulang harus dipisahkan.

## Rencana implementasi aman

### Fase A — Baseline dan pengujian
1. Simpan baseline branch dan commit produksi.
2. Catat metrik: waktu initial load, durasi query feed, jumlah baris/respons, jumlah event Realtime, dan jumlah pemanggilan `loadPosts`.
3. Buat skenario regresi untuk login, feed, like, komentar, misi Roulette, hadiah, wallet, ranking, Panel Progres, dan game.

### Fase B — Perbaikan performa frontend dengan risiko rendah
1. Terapkan pagination feed dengan urutan stabil dan penanganan data baru.
2. Pilih kolom yang diperlukan; jangan memakai `select('*')` untuk daftar besar jika tidak dibutuhkan.
3. Pisahkan initial load dari debounce refresh realtime 900 ms.
4. Batasi refresh berdasarkan event dan halaman yang sedang aktif.
5. Ukur ulang sebelum dan sesudah tiap perubahan.

### Fase C — Diagnosis
1. Buat logger terstruktur di frontend dengan modul, operasi, waktu, dan correlation/request ID.
2. Jangan simpan token, password, isi curhatan privat, atau data sensitif dalam log.
3. Tambahkan tabel log server hanya setelah skema, RLS, retensi, dan batas akses disepakati.
4. Hubungkan error frontend dan kegagalan RPC tanpa mencatat rahasia.

### Fase D — Backend dan central data
1. Audit skema transaksi pusat, entry, wallet, trigger, RPC, indeks, RLS, dan fungsi ranking.
2. Tetapkan sumber kebenaran untuk saldo, aktivitas, dan reward.
3. Periksa idempotency, transaksi atomik, dan jalur retry.
4. Jangan hapus ledger lama sampai rekonsiliasi membuktikan penggantinya lengkap.

### Fase E — Modularisasi dan deployment
1. Ekstrak modul satu per satu dari `index.html` tanpa mengubah perilaku.
2. Tambahkan unit/integration/regression tests.
3. Gunakan staging dan pull request.
4. Deploy bertahap dengan prosedur rollback.
5. Hapus implementasi lama hanya setelah penggunaan dan data berhasil direkonsiliasi.

## Hal yang belum boleh dilakukan

- Jangan menghapus tabel, trigger, RPC, atau ledger lama.
- Jangan mengubah saldo atau riwayat anggota untuk keperluan optimasi.
- Jangan memindahkan sumber ranking atau aktivitas sebelum rekonsiliasi.
- Jangan menghapus polling misi sebelum validasi event langsung terbukti.
- Jangan mengubah aturan transaksi, pembagian hasil, atau biaya.
- Jangan menerapkan perubahan performa besar langsung ke branch produksi tanpa pengujian.

## Langkah berikutnya

Audit database Supabase secara read-only: daftar tabel terkait, definisi RPC, trigger, policies, indeks, dan konfigurasi Realtime. Setelah peta backend lengkap, pilih satu perubahan berdampak tinggi dan berisiko rendah—kemungkinan pagination feed serta pemisahan initial load dari debounce realtime—lalu uji di staging.
