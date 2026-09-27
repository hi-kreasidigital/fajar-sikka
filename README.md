# Website Fajar Sikka

Website statis bilingual (Indonesia/Inggris) untuk Komunitas Fajar Sikka, Maumere, Flores.
Konten dikelola di **Airtable**, dibangun otomatis oleh **GitHub Actions**, dan dihosting gratis di **GitHub Pages**.

👉 **Panduan lengkap untuk pengurus (bahasa awam): buka `PANDUAN.html` di browser.**

## Cara kerja singkat

```
Airtable (isi konten) ──► GitHub Actions (06:07 & 18:07 WITA, atau tombol manual)
                              │  ambil data, unduh & kecilkan foto (WebP), susun halaman
                              ▼
                         GitHub Pages ──► pengunjung & Google (domain sendiri opsional)
```

## Struktur

| Berkas/folder | Isi |
|---|---|
| `site.config.json` | Pengaturan: alamat website (kosongkan = otomatis), ID base Airtable |
| `build.py` | Perintah untuk membangun website ke folder `dist/` |
| `generator/` | Kode penyusun halaman (Python) |
| `assets/` | CSS, JS, logo, dan foto lanskap Flores |
| `data/contoh.json` | Konten cadangan, dipakai bila `AIRTABLE_TOKEN` belum diatur |
| `.github/workflows/terbitkan.yml` | Jadwal & langkah build otomatis |

## Menjalankan di komputer sendiri (opsional)

```bash
pip install -r requirements.txt
python build.py --lihat                          # pakai data/contoh.json, buka http://localhost:8000
AIRTABLE_TOKEN=pat... python build.py --lihat    # pakai data asli dari Airtable
```

## Fitur SEO

- HTML statis cepat, foto WebP responsif (`srcset`), lazy-load
- Judul, meta description, canonical, Open Graph & Twitter Card per halaman
- `hreflang` Indonesia ↔ Inggris, `sitemap.xml` dengan alternatif bahasa, `robots.txt`, RSS
- Data terstruktur JSON-LD: `NGO`, `WebSite`, `Article`, `ImageGallery`, `BreadcrumbList`, `ItemList`

## Aturan konten

- Hanya baris berstatus **Terbit** yang tampil. Artikel dengan Tanggal Terbit di masa depan otomatis menunggu.
- Foto orang **hanya** tampil bila kolom **Izin Foto / Izin Publikasi** dicentang.
- Sisipkan foto di tengah artikel dengan `[foto:1]`, `[foto:2]`, … (urutan kolom *Foto Artikel*).
