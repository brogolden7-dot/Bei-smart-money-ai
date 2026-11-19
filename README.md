# BEI Smart Money AI — Prototype v0.1

Aplikasi Streamlit untuk screening awal saham BEI dari tablet Android.

## Isi folder
- `app.py` — aplikasi utama
- `requirements.txt` — daftar dependensi
- `universe_saham_template.csv` — template daftar ticker

## Menjalankan
1. Buat repository GitHub baru.
2. Upload ketiga file ini ke repository.
3. Buka https://share.streamlit.io dan login menggunakan GitHub.
4. Pilih **Create app**, pilih repository, branch `main`, dan file `app.py`.
5. Klik Deploy. Setelah selesai, buka URL `*.streamlit.app` dari Chrome Android.

## Format CSV universe
Kolom wajib:
- `ticker`: simbol Yahoo Finance, contoh `BBCA.JK`
- `kode`: kode saham, contoh `BBCA`
- `syariah`: `true` atau `false`

Template yang disertakan hanya berisi contoh ticker populer, BUKAN daftar lengkap BEI. Kolom syariah sengaja dikosongkan karena status DES belum diverifikasi. Isi `true` hanya untuk saham yang Anda cocokkan dengan DES OJK terbaru; isi `false` untuk saham yang dipastikan tidak masuk DES. Jangan menganggap status kosong sebagai non-syariah.

## Batasan versi awal
- Data harga berasal dari Yahoo Finance/yfinance; ketersediaan, keterlambatan, dan kelengkapan tidak dijamin.
- Field fundamental dari Yahoo Finance bisa kosong atau tidak konsisten.
- Proxy akumulasi menggunakan volume, posisi penutupan candle, dan arah OBV; bukan bukti transaksi bandar.
- Belum ada broker summary, net foreign flow, notifikasi, autentikasi pengguna, atau integrasi AI API.
- TP/SL pada versi awal hanya simulasi persentase, bukan level teknikal hasil analisis support/resistance.

## Catatan risiko
Aplikasi untuk riset dan edukasi, bukan saran beli/jual. Jangan menghubungkan aplikasi ini ke akun broker atau mengaktifkan auto-trading.
