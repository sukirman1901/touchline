# Perbandingan menyeluruh: mradovic vs SoccArt untuk Touchline

Tanggal: 2026-11-23. Tujuan: mengadopsi mesin analisis dari kedua proyek dengan
UI Touchline sekarang, bukan menyalin antarmuka demo.

## Kesimpulan

**Fondasi integrasi: mradovic. Sumber model dan analitik tambahan: SoccArt.**
Tidak ada bukti bahwa salah satu pipeline utuh lebih akurat/stabil pada Persibo.
Rekomendasi fondasi didasarkan pada pemisahan modul, kontrak data, dan kemudahan
adaptasi. Rekomendasi model SoccArt didasarkan pada ketersediaan bobot dan uji
lokal sebelumnya, bukan kemenangan benchmark terhadap model mradovic.

Risiko memasang seluruh source tanpa adaptasi: **tinggi**. Ada kesalahan
perhitungan, kegagalan pada input yang wajar, dependensi model yang belum
tersedia, dan perbedaan unit/kelas yang bisa merusak hasil diam-diam.

## Versi dan cakupan bukti

| Repo | Commit diperiksa |
|---|---|
| [mradovic38/football-analysis](https://github.com/mradovic38/football-analysis) | `1aaac243cc41924f80c0fc904cb0f1ce8c9ecc7d` |
| [adityapgupta/Sports-Analysis](https://github.com/adityapgupta/Sports-Analysis) | `f2256081e3f8257aeda5892935a983ffa6e28078` |

- Pemeriksaan entrypoint, detector, tracker, klasifikasi tim, anotasi, mapping,
  possession, speed, integrasi analitik, ekspor, dan dependensi.
- 13 probe deterministik langsung menjalankan modul source upstream.
- Hasil: `data/reference-comparison/probes.json`.
- Runner: `scripts/compare_reference_modules.py`.
- Uji Persibo sebelumnya memakai bobot SoccArt melalui adapter Touchline,
  **bukan** menjalankan pipeline SoccArt asli secara keseluruhan.
- Belum ada A/B full-video berlabel untuk kedua pipeline. Bobot detector/keypoint
  mradovic tidak ada pada checkout. SigLIP/kalibrasi penuh belum diuji lokal.
- Tidak ada klaim kualitas motion berdasarkan screenshot atau README demo.
- Ini penilaian adopsi source pada commit tersebut, bukan review PR/merge.

## Matriks fitur dan keputusan adopsi

| Fitur | mradovic | SoccArt | Pilihan Touchline / syarat |
|---|---|---|---|
| Orkestrasi | `FootballVideoProcessor`: detect → track → club → project → possession → speed → annotate | `main.py`: deteksi/cache → markers → smoothing → minimap → statistik | Struktur modul mradovic; output terstruktur masuk UI sekarang |
| Kontrak data | Dict per peran dan track, `bbox`, `club`, `club_color`, `projection`, `speed`, `has_ball` | Tuple ID/class/position dan pickle; class berubah menjadi team | Semantik mradovic, tambah timestamp, segment, confidence dan schema version |
| Model pemain | YOLO; bobot perlu disiapkan dari training | `players.pt` tersedia, kelas pemain/kiper/wasit/bola | Bobot SoccArt untuk baseline; pemetaan berdasarkan names model |
| Model bola | Bersama model objek; `ball_conf` terpisah setelah filtering deteksi | `ball.pt` khusus, pemilihan confidence tertinggi | Detector terpisah SoccArt; tambahkan temporal association, bukan max-confidence saja |
| Tracking ID | ByteTrack, `lost_track_buffer=5` | ByteTrack default | Satu ByteTrack, konfigurasi berdasarkan FPS sampel; benchmark fragmentasi |
| Re-ID / nomor jersey | Tidak tampak di pipeline utama | Notebook eksperimen + bobot; README mengatakan belum dideploy karena lambat | Bukan fitur siap pakai. Evaluasi terpisah, jangan klaim ID permanen |
| Tim | Crop jersey, masking rumput, KMeans, nearest configured RGB | SigLIP embedding → UMAP → KMeans | mradovic untuk baseline warna tim yang dikonfigurasi; A/B SigLIP sebagai opsi |
| Tim kiper | Centroid warna jersey kiper terpisah | Kedekatan kiper ke centroid posisi pemain tim | mradovic bila warna kiper diketahui; hindari menebak dari posisi saja |
| Wasit | Peran eksplisit dan ellipse putus-putus | Peran wasit tersedia; pemain/kiper digabung ke class tim | Pertahankan peran mradovic dalam schema |
| Busur dan label | Open ellipse 270°, ID track, double keeper, triangle owner | Supervision EllipseAnnotator dan TriangleAnnotator | mradovic: busur terbuka, warna tetap per tim. Penyesuaian user: tanpa outline hitam |
| Smoothing | Smoothing H dan speed; bukan player Re-ID | Weighted five-frame coordinate smoothing | SoccArt untuk posisi, dengan batas gap/shot dan timestamp tetap |
| Kalibrasi | 32 landmark YOLO → homography | No-Bells-Just-Whistles: landmark + garis → camera calibration | NBJW kandidat backend lebih lengkap; mradovic alternatif lebih sederhana. Belum ada pemenang akurasi |
| Minimap | Projection + Voronoi dalam output video | Minimap + visible pitch edges terpisah | View minimap mradovic di panel UI; source koordinat sesuai backend tervalidasi |
| Speed | Kecepatan real-time + moving average | DistanceAnalyzer + grafik profil kecepatan | mradovic untuk live metric, dengan perbaikan startup/gap; SoccArt untuk laporan |
| Jarak & sprint | Tidak tampak sebagai analitik lengkap di entrypoint | DistanceAnalyzer, SprintAnalyzer dan kategori intensitas | SoccArt setelah unit, waktu, gap dan persistensi ID benar |
| Possession | Proximity, grace period, live percentage | Event/zone/player possession analytics | Struktur state mradovic setelah hitungan ganda/grace diperbaiki; statistik waktu bukan jumlah panggilan |
| Pass yang benar terjadi | Tidak ada detector release-flight-reception lengkap | `passing.py` menilai kesempatan jalur umpan | Tidak ada modul siap pakai yang membuktikan completed passes; tetap kebutuhan tambahan |
| Passing opportunities | Tidak tampak | Lane, pressure, risk/reward, heuristic success score | SoccArt modul langsung setelah adapter diperbaiki; tampil sebagai opsi, bukan probabilitas terkalibrasi |
| Heatmap | Tidak tampak dalam pipeline utama | Player/team/ball heatmaps | SoccArt dengan perbaikan indeks dan larangan mengulang lokasi bola yang hilang |
| Kontrol ruang | Voronoi nearest-player | Voronoi + arrival-time/velocity control model | mradovic geometric territory dahulu; SoccArt advanced model setelah validasi |
| Simpan hasil | JSON, tetapi read/write seluruh file per frame | Pickle deteksi dan analitik | Semantik mradovic; penyimpanan atomik/SQLite Touchline |
| Ekspor | VideoWriter dari frame, preview OpenCV | Video markers/minimap, OpenCV/FFmpeg helper | Adopsi annotator, pertahankan FFmpeg Touchline untuk audio dan waktu sumber |
| UI review | Demo video / preview | Demo/plots/CLI | Tetap UI Touchline, editor dan koreksi pelatih |

## Hasil uji yang benar-benar dijalankan

Probe menggunakan input kecil terkontrol, bukan klip demo pilihan.

| Probe | Hasil teramati | Makna |
|---|---|---|
| mradovic centroid jersey merah/hitam | Kelas 0 / 1 sesuai | Dasar nearest-color bekerja pada warna terkontrol, belum bukti ketahanan crop nyata |
| mradovic speed konstan 7,2 km/jam | 7,2 setelah warm-up | Rumus metric speed benar pada lintasan bersih |
| mradovic startup speed | 1,44 saat kecepatan sebenarnya 7,2 | Window berisi nol membuat startup bias; bukan bukti detector salah |
| mradovic 1 frame possession | 2 update statistik | Penghitungan ganda terkonfirmasi |
| mradovic 3 landmark | OpenCV error | Tidak ada guard minimum korespondensi pada fungsi mapping |
| SoccArt smoothing posisi tetap | Tetap `(0.5, 0.5)` | Primitive smoothing lolos kasus dasar |
| SoccArt pemain away lebih dekat | Tetap memilih home | Bias urutan tim terkonfirmasi |
| SoccArt satu tim kosong | ValueError | Input tidak tertangani |
| SoccArt transfer dalam tim yang sama | Output player 2, event masih player 1 | Identitas event tidak mengikuti transfer |
| SoccArt 20 sampel bola hilang | Semua celah terisi interpolasi | Kontinuitas visual bisa tampak bagus meski tanpa observasi |
| SoccArt modul passing langsung | Menghasilkan satu opsi ke player 2 | Modul dasar berjalan pada input terkontrol |
| SoccArt wrapper passing | AttributeError `player_id` | Adapter memanggil atribut yang tidak ada (`passer_id` adalah nama sebenarnya) |
| SoccArt heatmap saat bola hilang di kanan | IndexError indeks 14 pada axis ukuran 10 | Indeks x/y tertukar di fallback |

## Temuan source penting dan perbaikan

### Prioritas 1 — sebelum hasil dipercayai

1. **mradovic possession dihitung ganda**:
   `ball_to_player_assignment/ball_to_player_assigner.py:134–145`.
   Satu frame menjalankan `add_possession` dua kali. Gunakan satu update per
   timestamp dengan durasi waktu; unknown harus masuk denominator yang jelas.
2. **SoccArt pemilik bola bias home**:
   `analytics/utils/ball.py:85–100`. Bandingkan jarak kedua tim, tangani seri
   sebagai contested, dan tangani array kosong.
3. **SoccArt same-team transfer salah pada event**:
   `analytics/utils/ball.py:149–160`. Pisahkan team possession dari player
   possession; perubahan player harus membuat interval baru.
4. **SoccArt interpolasi tanpa batas**:
   `tracking/interpolate.py:28–51`. Batasi durasi dan shot; simpan flag inferred.
   Loop hanya memeriksa objek pertama dan frame kosong dapat tidak menambah row.
5. **Homography mradovic tanpa validity gate**:
   `position_mappers/homography.py:47–69`. Tambahkan minimum landmark,
   degenerasi, RANSAC/error gate dan reset pada cut.
6. **Kelas model berbeda**:
   mradovic mengasumsikan `ball, goalkeeper, player, referee`;
   bobot SoccArt mempunyai `ball, player, goalkeeper, referee`.
   Jangan menyalin mapper indeks langsung; ini bisa menukar kiper/pemain.
7. **Bola confidence mradovic**:
   `tracking/object_tracker.py:45,114–116`; main memakai deteksi .5 dan ball .05.
   Threshold .05 tidak dapat memulihkan bola yang sudah tersaring pada .5.
8. **Passing/heatmap SoccArt wrapper gagal**:
   `analytics/integration.py:179,229–230`. Perbaiki nama atribut dan `[y][x]`;
   jangan isi heatmap dengan lokasi bola lama saat bola tidak teramati.

### Prioritas 2 — sebelum statistik pertandingan dan deployment

- Speed mradovic: default 100×50 m, clamp 40 km/jam, zero-filled mean, missing
  projection=0. Gunakan dimensi aktual, unknown, warm-up valid dan reset gap/shot.
- SoccArt speed/distance: `distance.py:80–83` perlu guard dt>0 dan gap; default
  konfigurasi 25 fps tidak boleh menggantikan FPS/timestamp input 30 fps.
- SoccArt smoother dipakai setelah `draw_markers` di main.py. Memiliki smoothing
  minimap tidak membuktikan overlay pemain pada video aslinya sudah dismoothing.
- SoccArt zone calculations menggunakan y melawan field_length; samakan sumbu
  longitudinal dan arah serangan untuk possession/control.
- Tim mradovic dihitung per crop per frame tanpa voting track. Tim SoccArt
  memakai clustering tanpa random seed pada UMAP/KMeans. Keduanya perlu
  konsistensi label antar-run, abstention dan temporal consensus.
- mradovic secara internal resize video ke 1920×1080 sebelum tracker; fixed
  dimensions konsisten di demo itu, tetapi tidak boleh langsung dipakai pada
  frame asli Touchline 1280×720.
- JSON writer mradovic menghapus output lama pada init dan menulis ulang semua
  data per frame. Pertahankan storage Touchline, terutama koreksi pelatih.
- SoccArt class_id diubah menjadi team sehingga informasi kiper bisa hilang.
  Role dan team harus menjadi dua field berbeda.
- NBJW model/line backend lebih kompleks; belum boleh disebut lebih stabil
  sampai diuji pada pencahayaan/angle Persibo.

## Apa yang dapat disebut lebih stabil saat ini?

**Terbukti pada probe kecil:** centroid jersey mradovic, steady metric speed
mradovic, weighted smoothing SoccArt, direct passing-opportunity SoccArt.

**Lebih mudah diintegrasikan berdasarkan source:** pipeline/role annotation
mradovic. Ini bukan klaim akurasi video.

**Sudah tersedia dan pernah diproses pada Persibo:** bobot pemain/bola SoccArt.
Hasil adapter terakhir: 750 sampel, 286 dengan kandidat bola, 179 observasi
lolos filter +18 interpolasi, 4 possession pendek, 0 pass. Belum cukup stabil.

**Belum ditentukan:** kualitas deteksi mradovic vs SoccArt, KMeans vs SigLIP
pada crop Persibo, YOLO landmarks vs NBJW, Re-ID dan identitas sepanjang match.

## Rencana adopsi kode, bukan sekadar meniru screenshot

1. Pin source revision dan simpan provenance/license pada modul yang diambil.
2. Gunakan kontrak role/team/projection mradovic sebagai adapter data; tetap
   timestamp sumber, normalized image coordinates dan metric pitch coordinates
   yang terpisah.
3. Adopsi modul ringan yang lolos probe: anotasi, centroid assignment opsional,
   speed estimator dengan patch regression. UI sekarang tetap konsumen data.
4. Pakai model SoccArt sebagai baseline detector. Simpan cache supaya pengujian
   tracker/possession tidak harus mengulang inference 20 menit.
5. Uji parameter ByteTrack dan team assignment pada frame yang sama; ukur ID
   switch/fragmentasi dan label tim, bukan hanya panjang garis yang tampil.
6. Perbaiki possession state dan agregasi waktu sebelum mengganti penanda aktif.
7. Siapkan bobot kalibrasi yang sah dan landmark layout yang cocok; evaluasi
   error proyeksi sebelum speed/minimap/heatmap.
8. Adopsi analitik SoccArt satu per satu melalui adapter yang dites. Pilihan
   umpan dan kontrol ruang diberi label heuristik.

### Matriks benchmark sebelum promosi ke UI

- Segmen sama: permainan terbuka, duel/occlusion, bola cepat, close-up dan cut.
- Label manual: bola, beberapa ID pemain, tim, pemilik/contested/unknown,
  landmark lapangan yang terlihat.
- Detector: precision/recall bola dan pemain; coverage saja tidak cukup.
- Tracker: ID switches, fragmentasi, lama track putus, pemulihan setelah occlusion.
- Team: kesalahan per-track dan perubahan label dalam track yang sama.
- Possession: pemilik benar, false ownership, jeda/flashing, lag perpindahan.
- Calibration: reprojection error dan fraksi frame valid; speed dicek setelahnya.
- Runtime: wall time, CPU/memory, FPS aktual pada perangkat yang sama.
- UI/export: schema sama, timing/audio sama, warna per tim tetap, hasil review
  tidak tertimpa. Demo yang tampak lebih ramai bukan metrik kelulusan.

## Lisensi dan dependensi adopsi

- mradovic: MIT, copyright Mihailo Radović 2024; pertahankan notice.
- SoccArt: tidak ditemukan lisensi root yang mencakup semua source/bobot.
  Lisensi nested evaluation tidak otomatis melisensikan seluruh repo.
  Klarifikasi izin sebelum menyalin/meredistribusi modul SoccArt sebagai bagian
  produk; evaluasi lokal saat ini tidak membuktikan hak distribusi.
- Keduanya memakai Ultralytics dan model/dataset eksternal dengan ketentuan
  masing-masing.
- mradovic requirements mem-pin torch CUDA (`2.4.1+cu118`); SoccArt berisi
  CUDA hard-code dan path Conda Linux. Buat environment Mac yang kompatibel,
  bukan menjalankan requirements upstream secara membabi buta.

## Batas hasil ini

13 probe ini menunjukkan perilaku fungsi tertentu dan reproduksi kegagalan,
bukan audit seluruh repo atau ranking akurasi semua fitur. README metrics
SoccArt adalah laporan penulis pada evaluasi mereka, bukan hasil pengukuran kita.
Fitur Re-ID masih eksperimen menurut README lokalnya. Tidak ada alasan untuk
menganggap ID track sebagai nomor jersey/nama pemain.

## Adopsi kode yang sudah dilakukan setelah perbandingan

- `app/vendor/mradovic/speed_estimator.py`: adaptasi kode estimator upstream,
  dengan revision, MIT license dan daftar perubahan di direktori yang sama.
- `app/motion.py`: adapter koordinat meter/timestamp; menolak lonjakan,
  memutus histori pada gap dan memisahkan ID antar-shot.
- `app/metrics.py`: sekarang memakai estimator adopsi tersebut untuk speed.
- Perbaikan terhadap upstream: startup tidak berisi nol buatan, data hilang
  menjadi unknown, kecepatan ekstrem ditolak alih-alih dijepit ke angka batas.
- Empat tes regresi motion ditambahkan; seluruh **34 tes lulus**.
- `git diff --check` bersih.
- Ini adopsi backend pertama yang diuji, bukan klaim semua fitur sudah diadopsi.
  Speed Persibo tetap menunggu kalibrasi valid. UI tidak diubah pada tahap ini.
