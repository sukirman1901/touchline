# Touchline

Ruang analisis sepak bola lokal untuk pelatih. Mulai dari upload video atau link
YouTube, pilih rentang klip, jalankan analisis, lalu review dan ekspor.
Proyek Persibo lama tetap tersedia jika file sumbernya ada di Mac.

## Jalankan

```sh
cd /Users/aaa/Documents/Developer/football-analytics
/Users/aaa/Downloads/.football-analyzer-py311/bin/python -m app.server
```

Buka **http://127.0.0.1:8876** di Chrome biasa. Alternatif: klik dua kali `Jalankan Touchline.command`, lalu buka alamat tersebut. Server harus tetap berjalan selama aplikasi dipakai. Jika port sudah digunakan, jalankan dengan `--port 8877`.

Python 3.11 dan FFmpeg/ffprobe diperlukan. Untuk pemasangan baru:

```sh
git clone https://github.com/sukirman1901/touchline.git
cd touchline
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-analysis.txt
python -m app.server
```

Pasang FFmpeg melalui package manager sistem (di Mac: `brew install ffmpeg`).
Letakkan model kompatibel `players.pt` dan `ball.pt` di `data/models/`.
Model dan video tidak disertakan dalam Git. Tanpa model, upload/preview tetap
bisa dipakai; tombol analisis akan menjelaskan model yang perlu disiapkan.
Tidak ada dependensi frontend eksternal, akun, API key, atau biaya cloud.

## Dari video ke workspace

1. Buka beranda `http://127.0.0.1:8876/`.
2. Pilih **Upload video** (maksimal 2 GB) atau **Link YouTube** untuk satu video.
3. Tunggu pengunduhan/penyiapan preview. Upload dikirim ke server lokal.
4. Putar preview dan isi **Mulai / Selesai** dalam detik; default maksimal 60 detik.
5. Klik **Mulai analisis**. Halaman menunjukkan tahap dan progres detector.
6. Klik **Buka ruang analisis** saat hasil siap.
7. Proyek bisa dibuka kembali dari **Proyek tersimpan**. Jika proses gagal,
   detail dan tombol **Coba lagi** tersedia. Server harus tetap berjalan.

YouTube memakai yt-dlp (modul Python atau executable). Video privat, pembatasan
akses atau perubahan YouTube bisa membuat download gagal; UI menyediakan
pesan error dan upload sebagai alternatif. Preview disiapkan ke H.264/AAC
untuk playback browser, sehingga video panjang memerlukan waktu tambahan.

Setiap proyek memiliki `data/projects/<id>/`: manifest, video sumber/preview,
klip, hasil otomatis dan database koreksi. Proyek diidentifikasi di URL
`/workspace?project=<id>`; media, event dan ekspor terisolasi antar-tab.
Proyek Persibo sebelumnya ada di `/workspace?project=legacy`.

## Workflow

1. Putar video. `Space` untuk putar/jeda, tombol panah untuk melangkah satu frame.
2. Pilih **Tandai kejadian** dan pilih umpan atau penguasaan.
3. Untuk koreksi manual, klik **Pilih posisi awal**, lalu klik kaki pemain pada video. Posisi dan waktu dicatat.
4. Majukan video, klik **Pilih posisi akhir**, lalu klik posisi penerima/akhir. Alternatif keyboard: buka **Edit koordinat tanpa klik video**.
5. Pilih hasil umpan dan isi catatan. Centang **Sudah saya periksa di video** setelah review.
6. Simpan. Kejadian bisa dibuka kembali lewat daftar atau penanda timeline.
7. **Ekspor video** menghasilkan MP4 dengan anotasi terverifikasi dan audio asli. Draf, observasi AI mentah, serta antarmuka aplikasi tidak masuk ekspor.

## Analisis otomatis

Jalankan pemrosesan offline pada klip lokal:

```sh
/Users/aaa/Downloads/.football-analyzer-py311/bin/python -m app.analyze
```

Deteksi pemain beresolusi tinggi dan empat tile bola diproses pada sekitar 10 fps.
Model lokal: `~/Downloads/yolo11n.pt`. Lingkungan analyzer memerlukan Ultralytics,
PyTorch dan Supervision yang sudah tersedia. Waktu proses bergantung CPU.

Untuk evaluasi lokal dengan model sepak bola SoccArt yang sudah disimpan:

```sh
/Users/aaa/Downloads/.football-analyzer-py311/bin/python -m app.analyze --model data/models/players.pt --ball-model data/models/ball.pt --sample-fps 10
```

Asal dan hash model dicatat di `data/models/provenance.json`. Model khusus memakai
detektor bola full-frame 640 dan kandidat bola dari model pemain 960. Filter
kontinuitas menolak lompatan jauh dan kandidat di badan pemain; ini juga dapat
melewatkan bola udara. Smoothing pemain dibatasi ID/segmen; interpolasi bola
hanya mengisi celah pendek. UI menampilkan progres dan mempertahankan hasil
sebelumnya selama pemrosesan. Bobot eksternal hanya untuk evaluasi lokal.

Hasil tersimpan di `data/automatic.json`; `data/automatic.detections.json` menyimpan
deteksi mentah untuk evaluasi ulang. Hash sumber diverifikasi server.
Setelah proses selesai, refresh workspace:
- Kandidat penguasaan dan umpan masuk timeline tanpa penandaan manual.
- Busur dan segitiga pembawa bola mengikuti warna tim; jejak bola memakai cyan.
- Kandidat umpan menggunakan jejak bola pendek yang memudar.
- Buka kejadian untuk memeriksa hasil, mengoreksi, atau menghapusnya.
- Koreksi dan penghapusan tersimpan terpisah dari hasil detector.
- Ekspor tetap hanya memasukkan kejadian yang telah diperiksa.

## Data dan batas analisis

### Pipeline terpadu (integrasi berlangsung)

Skema hasil versi 2 menambahkan `teams`, `modules`, `players` dan `metrics`.
Kelompok jersey memakai observasi torso dan median per track, bukan identitas
klub terverifikasi. Kiper tanpa konfigurasi jersey khusus tetap belum bertim.
Renderer pemain kini terpisah dari daftar kejadian; label `T` adalah ID track.

Adapter landmark menerima `--pitch-model model-pose.pt --pitch-layout layout.json`.
Layout harus cocok dengan **urutan indeks model**, dengan `length`, `width` dalam
meter dan `points` berupa daftar `[x_m, y_m]`. Jangan menggunakan layout model
lain meskipun jumlah titik sama. Bobot landmark belum tersedia lokal.

Homography divalidasi sebelum speed/jarak, heatmap waktu, wilayah terdekat dan
jalur umpan geometris dihitung. Modul-modul tersebut belum dievaluasi pada Persibo.
UI minimap/speed menunggu kalibrasi valid; tampilan heatmap/territory dan ekspor
lapisan semua pemain masih merupakan pekerjaan integrasi lanjutan.

- `data/project.sqlite`: kejadian dan koreksi pelatih; tersimpan setelah reload.
- `exports/`: MP4 hasil ekspor. Nama unik; file sumber tidak ditimpa.
- Sumber: `~/Downloads/Gol_1_Persibo_Sehabudin.mp4`.
- Observasi: `~/Downloads/tracking_Gol_1_Persibo_Sehabudin.csv`.
- Kandidat otomatis menggunakan heuristik kedekatan bola dan kontinuitas track.
  Kedekatan tidak membuktikan penguasaan atau niat mengumpan. Hasil umpan tetap
  unknown sampai diperiksa; statistik keberhasilan tidak dibuat dari tebakan.
- Label gol/nama klip berasal dari skrip input, bukan hasil klasifikasi gol.
- Warna Cluster A/B belum merupakan identitas tim terverifikasi. `T123` adalah track sementara, bukan nomor punggung.
- Baseline lama: bola teramati di 87 dari 1.125 frame sampel (7,7%). Hasil detector
  baru melaporkan denominator dan jumlah tersaring sendiri; cakupan bukan akurasi.
- Interpolasi overlay dibatasi 0,21 detik, ID pemain dan segmen kamera yang sama.
  Deteksi cut menggunakan perubahan visual dan dapat melewatkan cut atau menandai
  gerak cepat sebagai cut. Pelacakan dan filter belum dievaluasi pada ground truth.
- Posisi merupakan koordinat gambar; belum ada kompensasi kamera/perspektif lapangan.
  Estimasi possession memerlukan beberapa sampel konsisten dan menolak bola
  diperebutkan. Cincin tidak dipertahankan saat bukti hilang.
- Anotasi manual tetap memakai dua anchor; anotasi otomatis memakai lintasan sampel.
- Persentase sukses hanya memakai umpan yang direview dengan hasil diketahui. Umpan unknown dan belum direview ditampilkan terpisah; kedua kelompok dapat beririsan.
- Homography/speed tersedia sebagai adapter bersyarat, tetapi bobot landmark
  dan validasi Persibo belum tersedia. Tidak ada identitas pemain lintas cut
  atau penilaian keputusan taktis otomatis.
- Ekspor dibulatkan ke batas frame. Posisi overlay berbagi koordinat normalisasi yang sama dengan browser.

## Verifikasi

```sh
/Users/aaa/Downloads/.football-analyzer-py311/bin/python -m unittest discover -s tests -v
```

Tes mencakup sinkronisasi frame, validasi event, persistensi SQLite, denominator statistik, HTTP range/traversal, interval anotasi dan ekspor dengan audio. Lihat `docs/first-clip-review.md` untuk bukti browser dan batas cakupan.
