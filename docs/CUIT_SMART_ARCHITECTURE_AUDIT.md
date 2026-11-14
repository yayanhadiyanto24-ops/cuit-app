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


## Lampiran — Pemeriksaan Supabase read-only

Project yang diperiksa: `CUIT` (`ozakuxlktqweembeqgyh`), status `ACTIVE_HEALTHY`, PostgreSQL 17.11. Pemeriksaan ini bersifat baca-saja; tidak ada SQL DDL/DML yang dijalankan.

### Inventaris database
- 52 tabel pada schema `public`.
- 25 migration tercatat.
- 82 fungsi pada schema `public`.
- 118 indeks pada schema `public`.
- 54 policy RLS pada schema `public`.
- Trigger terdeteksi pada 11 tabel, total 16 trigger:
  `comments`, `cuit_checkins`, `cuit_post_gift_ledger`,
  `cuit_roulette_question_attempts`, `cuit_roulette_spins`,
  `curhat`, `follows`, `gift_transactions`, `post_likes`,
  `profiles`, dan `reels_claims`.

### Temuan Supabase Performance Advisor

| Temuan | Jumlah | Prioritas tindak lanjut |
|---|---:|---|
| Foreign key belum memiliki indeks penutup | 16 | Tinjau query dan tambah indeks yang memang mendukung beban nyata |
| RLS auth initplan | 14 | Evaluasi policy agar pemanggilan auth function tidak dievaluasi per baris |
| Indeks belum pernah digunakan | 7 | Jangan langsung dihapus; cek periode observasi dan query workload |
| Multiple permissive policies | 21 | Audit duplikasi dan gabungkan hanya bila semantik akses tetap sama |
| Duplicate index | 1 | `cuit_topup_ledger`: `cuit_topup_ledger_order_id_key` dan `cuit_topup_ledger_order_unique` terdeteksi identik; verifikasi constraint dan dependensi sebelum perubahan |

### Temuan Supabase Security Advisor

| Temuan | Jumlah | Makna |
|---|---:|---|
| RLS aktif tanpa policy | 18 tabel | Secara default akses API ditolak; pastikan ini disengaja dan tidak memutus fungsi yang diperlukan |
| SECURITY DEFINER dapat dipanggil role anon | 22 fungsi | Perlu audit EXECUTE grants dan pemeriksaan identitas/otorisasi di body fungsi |
| SECURITY DEFINER dapat dipanggil role authenticated | 51 fungsi | Perlu audit per fungsi; SECURITY DEFINER bisa benar untuk RPC transaksi, tetapi harus dibatasi dengan benar |
| Ekstensi `pg_net` berada di schema public | 1 | Tinjau penempatan dan kebutuhan ekstensi |
| Leaked password protection nonaktif | 1 | Pertimbangkan mengaktifkannya melalui pengaturan Auth |

**Peringatan penting:** Advisor tidak otomatis berarti semua SECURITY DEFINER adalah celah. CUIT memakai RPC transaksi yang memang mungkin membutuhkan hak istimewa. Kita harus memeriksa body fungsi, `search_path`, validasi `auth.uid()`, hak EXECUTE untuk anon/authenticated, dan skenario pemanggilan sebelum mengubah grants. Jangan mencabut EXECUTE secara massal karena dapat mematikan transaksi, reward, game, atau login.

### Fungsi pusat yang dikonfirmasi ada

Fungsi berikut ditemukan di database dan berjalan sebagai SECURITY DEFINER:
- `cuit_central_record_transaction(...)`
- `cuit_central_get_activity_ranking(...)`
- `cuit_roulette_claim_mission(...)`
- `cuit_pay_like(...)`
- `cuit_submit_comment_transaction(...)`
- `cuit_submit_comment_thread_transaction(...)`
- `cuit_send_post_gift(...)`

Daftar ini mengonfirmasi bahwa titik pusat transaksi, ranking, like, komentar, hadiah, dan misi memang tersedia. Definisi dan hak aksesnya masih perlu diperiksa secara individual.

### Prioritas baru berdasarkan temuan nyata

1. **P0 — Keamanan RPC:** audit 22 fungsi SECURITY DEFINER yang dapat dipanggil anon. Tentukan mana yang harus publik, authenticated-only, atau admin-only; periksa validasi identitas dan otorisasi sebelum mengubah grants.
2. **P1 — Feed:** pagination dan pemilihan kolom karena frontend sekarang mengambil semua baris curhat.
3. **P1 — Realtime:** kurangi refresh feed global akibat event komentar/follow; pertahankan update saldo dan aktivitas akun sendiri.
4. **P1 — Debounce:** pisahkan initial feed load dari wrapper 900 ms.
5. **P2 — Database performance:** tinjau 16 foreign key tanpa indeks dan 14 policy RLS initplan.
6. **P2 — RLS policy:** tinjau 21 kelompok multiple permissive policy tanpa mengubah cakupan akses.
7. **P3 — Cleanup indeks:** verifikasi duplicate index dan unused indexes berdasarkan workload, lalu buat migrasi terpisah.

Audit berikutnya harus mengambil definisi SQL fungsi RPC kritis, trigger, policy, dan indeks yang relevan. Belum ada perubahan database yang dilakukan.
