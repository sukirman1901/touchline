# Touchline

Ruang analisis sepak bola lokal untuk pelatih. Versi pertama menggunakan klip Persibo berdurasi 75 detik dan CSV observasi yang sudah tersedia di Downloads.

## Jalankan

```sh
cd /Users/aaa/Documents/Developer/football-analytics
/Users/aaa/Downloads/.football-analyzer-py311/bin/python -m app.server
```

Buka **http://127.0.0.1:8876** di Chrome biasa. Alternatif: klik dua kali `Jalankan Touchline.command`, lalu buka alamat tersebut. Server harus tetap berjalan selama aplikasi dipakai. Jika port sudah digunakan, jalankan dengan `--port 8877`.

Python 3.11 dan FFmpeg diperlukan. Workspace hanya membutuhkan OpenCV dan NumPy; lingkungan analyzer yang telah dipasang sudah menyediakannya. Tidak ada dependensi frontend eksternal, akun, API key, atau biaya cloud.

## Workflow

1. Putar video. `Space` untuk putar/jeda, tombol panah untuk melangkah satu frame.
2. Pilih **Tandai kejadian** dan pilih umpan atau penguasaan.
3. Klik **Pilih posisi awal**, lalu klik kaki pemain pada video. Posisi dan waktu dicatat.
4. Majukan video, klik **Pilih posisi akhir**, lalu klik posisi penerima/akhir. Alternatif keyboard: buka **Edit koordinat tanpa klik video**.
5. Pilih hasil umpan dan isi catatan. Centang **Sudah saya periksa di video** setelah review.
6. Simpan. Kejadian bisa dibuka kembali lewat daftar atau penanda timeline.
7. **Ekspor video** menghasilkan MP4 dengan anotasi terverifikasi dan audio asli. Draf, observasi AI mentah, serta antarmuka aplikasi tidak masuk ekspor.

## Data dan batas versi awal

- `data/project.sqlite`: kejadian dan koreksi pelatih; tersimpan setelah reload.
- `exports/`: MP4 hasil ekspor. Nama unik; file sumber tidak ditimpa.
- Sumber: `~/Downloads/Gol_1_Persibo_Sehabudin.mp4`.
- Observasi: `~/Downloads/tracking_Gol_1_Persibo_Sehabudin.csv`.
- Ini workspace **review semi-manual**, bukan deteksi penguasaan dan operan otomatis.
- Label gol/nama klip berasal dari skrip input, bukan hasil klasifikasi gol.
- Warna Cluster A/B belum merupakan identitas tim terverifikasi. `T123` adalah track sementara, bukan nomor punggung.
- Bola teramati di 87 dari 1.125 frame sampel (7,7%). Nilai ini adalah cakupan deteksi, bukan akurasi model.
- Observasi pemain ditahan maksimal satu frame sumber yang dilewati. Tidak mengisi kehilangan bola panjang.
- Garis umpan adalah hubungan dua titik manual pada gambar. Gerak kamera tidak dikompensasi; jangan menafsirkannya sebagai lintasan bola atau jarak fisik.
- Lingkaran penguasaan bergerak linear di antara dua titik manual. Pecah interval untuk perubahan arah/kamera.
- Persentase sukses hanya memakai umpan yang direview dengan hasil diketahui. Umpan unknown dan belum direview ditampilkan terpisah; kedua kelompok dapat beririsan.
- Tidak ada homography, radar, speed, acceleration, identitas lintas cut, atau penilaian keputusan taktis otomatis.
- Ekspor dibulatkan ke batas frame. Posisi overlay berbagi koordinat normalisasi yang sama dengan browser.

## Verifikasi

```sh
/Users/aaa/Downloads/.football-analyzer-py311/bin/python -m unittest discover -s tests -v
```

Tes mencakup sinkronisasi frame, validasi event, persistensi SQLite, denominator statistik, HTTP range/traversal, interval anotasi dan ekspor dengan audio. Lihat `docs/first-clip-review.md` untuk bukti browser dan batas cakupan.
