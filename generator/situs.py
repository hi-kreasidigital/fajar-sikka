"""Penyusun website Fajar Sikka: data Airtable -> halaman HTML statis."""
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import unicodedata
import urllib.parse
from zoneinfo import ZoneInfo

from . import markdown as md
from .airtable import ambil_semua
from .media import Media
from .teks import BIDANG_EN, BULAN, LANSKAP, LOGO, T

LANGS = ("id", "en")
RUTE = {
    "home": {"id": "/", "en": "/en/"},
    "tentang": {"id": "/tentang/", "en": "/en/about/"},
    "program": {"id": "/program/", "en": "/en/programs/"},
    "kabar": {"id": "/kabar/", "en": "/en/news/"},
    "galeri": {"id": "/galeri/", "en": "/en/gallery/"},
    "mitra": {"id": "/mitra/", "en": "/en/partners/"},
    "dukung": {"id": "/dukung/", "en": "/en/support/"},
    "kontak": {"id": "/kontak/", "en": "/en/contact/"},
}
DETAIL = {
    "program": {"id": "/program/{}/", "en": "/en/programs/{}/"},
    "kabar": {"id": "/kabar/{}/", "en": "/en/news/{}/"},
    "kategori": {"id": "/kabar/kategori/{}/", "en": "/en/news/category/{}/"},
    "halaman": {"id": "/kabar/halaman/{}/", "en": "/en/news/page/{}/"},
    "galeri": {"id": "/galeri/{}/", "en": "/en/gallery/{}/"},
}
PER_HALAMAN = 12
e = html.escape


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80] or "item"


def unik(items, key="slug"):
    seen = set()
    for it in items:
        base, n = it[key], 2
        while it[key] in seen:
            it[key] = f"{base}-{n}"
            n += 1
        seen.add(it[key])


# ======================================================================
class Situs:
    def __init__(self, root):
        self.root = root
        with open(os.path.join(root, "site.config.json"), encoding="utf-8") as f:
            self.cfg = json.load(f)
        alamat = (self.cfg.get("alamat_website") or os.environ.get("SITE_URL")
                  or os.environ.get("PAGES_BASE_URL") or "http://localhost:8000").strip()
        p = urllib.parse.urlparse(alamat if "://" in alamat else "https://" + alamat)
        self.origin = f"{p.scheme}://{p.netloc}"
        self.host = p.netloc
        self.base = p.path.rstrip("/")
        self.dist = os.path.join(root, "dist")
        self.cache = os.path.join(root, ".cache")
        tz = ZoneInfo(self.cfg.get("zona_waktu") or "Asia/Makassar")
        self.now = dt.datetime.now(tz)
        self.today = self.now.date()
        self.sitemap = []
        self.org = self.cfg.get("nama_organisasi", "Fajar Sikka")

    # ---------- URL ----------
    def u(self, path):
        return self.base + path

    def abs(self, path):
        if path.startswith("http"):
            return path
        return self.origin + self.base + path

    # ---------- build ----------
    def bangun(self):
        print(f"→ Alamat website: {self.origin}{self.base or ''}/")
        data, sumber = ambil_semua(self.cfg.get("airtable_base_id"), os.environ.get("AIRTABLE_TOKEN"), self.root)
        print(f"→ Sumber konten: {'Airtable' if sumber == 'airtable' else 'data/contoh.json (AIRTABLE_TOKEN belum diatur)'}")
        if os.path.exists(self.dist):
            shutil.rmtree(self.dist)
        os.makedirs(self.dist)
        self.media = Media(self.dist, self.cache, self.u)
        self._aset()
        self._siapkan(data)
        for lang in LANGS:
            self.lang = lang
            self.t = T[lang]
            self.hal_beranda()
            self.hal_tentang()
            self.hal_program()
            self.hal_kabar()
            self.hal_galeri()
            self.hal_mitra()
            self.hal_dukung()
            self.hal_kontak()
            self.rss()
        self.lang, self.t = "id", T["id"]
        self.hal_404()
        self.berkas_seo()
        if self.media.gagal:
            print("⚠ Foto yang gagal diproses:")
            for g in self.media.gagal:
                print("   -", g)
        for w in self.peringatan:
            print("⚠", w)
        n = sum(len(fs) for _, _, fs in os.walk(self.dist))
        print(f"✓ Selesai: {len(self.sitemap)} halaman, {n} berkas di folder dist/")

    # ---------- aset statis ----------
    def _aset(self):
        a = os.path.join(self.root, "assets")
        os.makedirs(os.path.join(self.dist, "aset"), exist_ok=True)
        for nama in ("style.css", "site.js"):
            with open(os.path.join(a, nama), "rb") as f:
                isi = f.read()
            h = hashlib.sha1(isi).hexdigest()[:8]
            base, ext = os.path.splitext(nama)
            tujuan = f"/aset/{base}.{h}{ext}"
            with open(self.dist + tujuan, "wb") as f:
                f.write(isi)
            setattr(self, "url_" + base.replace("site", "js").replace("style", "css"), self.u(tujuan))
        for f in os.listdir(os.path.join(a, "logo")):
            shutil.copyfile(os.path.join(a, "logo", f), os.path.join(self.dist, "aset", f))
        shutil.copyfile(os.path.join(a, "og-default.jpg"), os.path.join(self.dist, "aset", "og-default.jpg"))
        self.lanskap = {}
        for k, (f, alt) in LANSKAP.items():
            self.lanskap[k] = (self.media.dari_file(os.path.join(a, "foto", f), "flores-" + os.path.splitext(f)[0], og=True), alt)
        with open(os.path.join(self.dist, ".nojekyll"), "w") as f:
            f.write("")

    # ---------- olah data ----------
    def _siapkan(self, d):
        self.peringatan = []
        F = lambda r, k, dflt="": (r["fields"].get(k) if r["fields"].get(k) not in (None, "") else dflt)

        # Pengaturan
        self.P = {}
        for r in d["Pengaturan"]:
            k = (F(r, "Kunci") or "").strip()
            if k:
                idv = (F(r, "Isi ID") or "").strip()
                self.P[k] = {"id": idv, "en": (F(r, "Isi EN") or "").strip() or idv}

        # Kategori
        self.kategori = {}
        for r in d["Kategori"]:
            nama = F(r, "Nama")
            if not nama:
                continue
            self.kategori[r["id"]] = {"id": r["id"], "nama": {"id": nama, "en": F(r, "Nama EN") or nama},
                                      "slug": slugify(F(r, "Slug") or nama), "artikel": []}
        unik(list(self.kategori.values()))

        # Mitra
        self.mitra = {}
        for r in d["Mitra"]:
            if not F(r, "Nama"):
                continue
            logo = next(iter(F(r, "Logo", []) or []), None)
            self.mitra[r["id"]] = {
                "nama": F(r, "Nama"),
                "kerja": {"id": F(r, "Bentuk Kerja Sama"), "en": F(r, "Bentuk Kerja Sama EN") or F(r, "Bentuk Kerja Sama")},
                "web": F(r, "Website"), "urut": F(r, "Urutan", 999), "tampil": bool(F(r, "Tampilkan", False)),
                "logo": self.media.dari_lampiran(logo) if logo else None,
            }
        self.mitra_tampil = sorted([m for m in self.mitra.values() if m["tampil"]], key=lambda m: (m["urut"], m["nama"]))

        # Program
        self.program = []
        for r in d["Program"]:
            if F(r, "Status") != "Terbit" or not F(r, "Nama"):
                continue
            izin = bool(F(r, "Izin Foto", False))
            fotos = F(r, "Foto", []) or []
            if fotos and not izin:
                self.peringatan.append(f"Program '{F(r, 'Nama')}' punya foto tetapi 'Izin Foto' belum dicentang — foto tidak ditampilkan.")
            fotos = [self.media.dari_lampiran(a, og=(i == 0)) for i, a in enumerate(fotos)] if izin else []
            nama_id = F(r, "Nama")
            self.program.append({
                "id": r["id"], "slug": slugify(F(r, "Slug") or nama_id),
                "nama": {"id": nama_id, "en": F(r, "Nama EN") or nama_id},
                "ringkas": {"id": F(r, "Ringkasan"), "en": F(r, "Ringkasan EN") or F(r, "Ringkasan")},
                "desk": {"id": F(r, "Deskripsi"), "en": F(r, "Deskripsi EN") or F(r, "Deskripsi")},
                "periode": F(r, "Periode"), "tahun": F(r, "Tahun", None), "lokasi": F(r, "Lokasi"),
                "bidang": F(r, "Bidang"), "mitra": [self.mitra[m] for m in F(r, "Mitra", []) or [] if m in self.mitra],
                "foto": [f for f in fotos if f], "album": [],
            })
        self.program.sort(key=lambda p: (-(p["tahun"] or 9999), p["nama"]["id"]))
        unik(self.program)
        prog_by_id = {p["id"]: p for p in self.program}

        # Artikel
        self.artikel = []
        for r in d["Artikel"]:
            if F(r, "Status") != "Terbit" or not F(r, "Judul"):
                continue
            try:
                tgl = dt.date.fromisoformat(str(F(r, "Tanggal Terbit") or "")[:10])
            except ValueError:
                self.peringatan.append(f"Artikel '{F(r, 'Judul')}' belum punya Tanggal Terbit — tidak diterbitkan.")
                continue
            if tgl > self.today:
                continue  # terjadwal
            izin = bool(F(r, "Izin Foto", False))
            sampul_att = next(iter(F(r, "Foto Sampul", []) or []), None)
            foto_att = F(r, "Foto Artikel", []) or []
            if (sampul_att or foto_att) and not izin:
                self.peringatan.append(f"Artikel '{F(r, 'Judul')}' punya foto tetapi 'Izin Foto' belum dicentang — foto tidak ditampilkan.")
            judul_id = F(r, "Judul")
            ada_en = bool(F(r, "Judul EN") and F(r, "Isi EN"))
            a = {
                "id": r["id"], "slug": slugify(F(r, "Slug") or judul_id), "tgl": tgl,
                "judul": {"id": judul_id, "en": F(r, "Judul EN") or judul_id},
                "ringkas": {"id": F(r, "Ringkasan") or md.excerpt(F(r, "Isi")),
                            "en": F(r, "Ringkasan EN") or md.excerpt(F(r, "Isi EN"))},
                "isi": {"id": F(r, "Isi"), "en": F(r, "Isi EN")},
                "ada_en": ada_en, "penulis": F(r, "Penulis"),
                "kategori": [self.kategori[k] for k in F(r, "Kategori", []) or [] if k in self.kategori],
                "sampul": self.media.dari_lampiran(sampul_att, og=True) if (sampul_att and izin) else None,
                "alt": F(r, "Keterangan Foto Sampul") or judul_id,
                "foto": [self.media.dari_lampiran(x) for x in foto_att] if izin else [],
                "seo_judul": F(r, "SEO Judul"), "seo_desk": F(r, "SEO Deskripsi"),
            }
            self.artikel.append(a)
        self.artikel.sort(key=lambda a: (a["tgl"], a["judul"]["id"]), reverse=True)
        unik(self.artikel)
        for a in self.artikel:
            for k in a["kategori"]:
                k["artikel"].append(a)

        # Galeri
        self.galeri = []
        for r in d["Galeri"]:
            if F(r, "Status") != "Terbit" or not F(r, "Judul"):
                continue
            if not F(r, "Izin Publikasi", False):
                self.peringatan.append(f"Album '{F(r, 'Judul')}' belum dicentang 'Izin Publikasi' — tidak ditampilkan.")
                continue
            atts = F(r, "Foto", []) or []
            fotos = [f for f in (self.media.dari_lampiran(x, og=(i == 0)) for i, x in enumerate(atts)) if f]
            if not fotos:
                continue
            try:
                tgl = dt.date.fromisoformat(str(F(r, "Tanggal") or "")[:10])
            except ValueError:
                tgl = None
            judul_id = F(r, "Judul")
            g = {"id": r["id"], "slug": slugify(F(r, "Slug") or judul_id), "tgl": tgl,
                 "judul": {"id": judul_id, "en": F(r, "Judul EN") or judul_id},
                 "ket": {"id": F(r, "Keterangan"), "en": F(r, "Keterangan EN") or F(r, "Keterangan")},
                 "lokasi": F(r, "Lokasi"), "foto": fotos,
                 "program": [prog_by_id[p] for p in F(r, "Program", []) or [] if p in prog_by_id]}
            self.galeri.append(g)
            for p in g["program"]:
                p["album"].append(g)
        self.galeri.sort(key=lambda g: (g["tgl"] or dt.date.min, g["judul"]["id"]), reverse=True)
        unik(self.galeri)

        # Pengurus
        self.pengurus = []
        for r in d["Pengurus"]:
            if not F(r, "Tampilkan", False) or not F(r, "Nama"):
                continue
            ft = next(iter(F(r, "Foto", []) or []), None)
            self.pengurus.append({"nama": F(r, "Nama"),
                                  "jabatan": {"id": F(r, "Jabatan"), "en": F(r, "Jabatan EN") or F(r, "Jabatan")},
                                  "kelompok": F(r, "Kelompok") or "Pengurus Inti", "urut": F(r, "Urutan", 999),
                                  "foto": self.media.dari_lampiran(ft) if ft else None})
        self.pengurus.sort(key=lambda p: (p["urut"], p["nama"]))

    # ---------- bantu ----------
    def p(self, key):
        return (self.P.get(key) or {}).get(self.lang, "")

    def r(self, nama):
        return RUTE[nama][self.lang]

    def rd(self, jenis, slug, lang=None):
        return DETAIL[jenis][lang or self.lang].format(slug)

    def tgl(self, d):
        if not d:
            return ""
        return f"{d.day} {BULAN[self.lang][d.month - 1]} {d.year}"

    def bidang(self, b):
        return BIDANG_EN.get(b, b) if self.lang == "en" else b

    def img(self, im, alt, sizes="100vw", cls="", eager=False):
        if not im:
            return ""
        c = f' class="{cls}"' if cls else ""
        load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
        return (f'<img{c} src="{im.src}" srcset="{im.srcset}" sizes="{sizes}" width="{im.w}" height="{im.h}" '
                f'alt="{e(alt)}" {load}>')

    def fl(self, k):
        """Foto lanskap bawaan -> (Img, alt)."""
        im, alt = self.lanskap[k]
        return im, alt[self.lang]

    def baris(self, key):
        return [x.strip() for x in self.p(key).split("\n") if x.strip()]

    def paragraf(self, teks):
        return "".join(f"<p>{e(x.strip())}</p>" for x in re.split(r"\n\s*\n", teks or "") if x.strip())

    # ---------- tata letak ----------
    def tulis(self, path, isi):
        tujuan = os.path.join(self.dist, path.lstrip("/"))
        if tujuan.endswith("/"):
            tujuan += "index.html"
        os.makedirs(os.path.dirname(tujuan), exist_ok=True)
        with open(tujuan, "w", encoding="utf-8") as f:
            f.write(isi)

    def halaman(self, path, judul, desk, isi, alt=None, og=None, tipe="website", ld=None,
                aktif=None, indeks=True, lastmod=None, judul_penuh=None, remah=None):
        """alt: {lang: path} halaman padanan bahasa lain."""
        t, lang = self.t, self.lang
        alt = alt or {lang: path}
        alt[lang] = path
        judul_tag = judul_penuh or (f"{judul} — {self.org}" if judul else self.org)
        desk = (desk or "").strip()
        if len(desk) < 70:
            akhir = ("Fajar Sikka — komunitas di Maumere, Flores, Nusa Tenggara Timur." if lang == "id"
                     else "Fajar Sikka — a community in Maumere, Flores, East Nusa Tenggara, Indonesia.")
            desk = f"{desk.rstrip('.')}. {akhir}" if desk else akhir
        og_url = self.abs(og) if og else self.abs("/aset/og-default.jpg")
        head_alt = ""
        if len(alt) > 1:
            for l2, p2 in alt.items():
                head_alt += f'<link rel="alternate" hreflang="{l2}" href="{e(self.abs(p2))}">\n'
            head_alt += f'<link rel="alternate" hreflang="x-default" href="{e(self.abs(alt.get("id", path)))}">\n'
        lainnya = "en" if lang == "id" else "id"
        tukar = alt.get(lainnya) or RUTE["home"][lainnya]
        lds = list(ld or [])
        if remah:
            lds.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": n, "item": self.abs(pp)}
                for i, (n, pp) in enumerate([(t["beranda"], self.r("home"))] + remah)]})
        ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in lds)
        nav = [("tentang", t["tentang"]), ("program", t["program"]), ("kabar", t["kabar"]),
               ("galeri", t["galeri"]), ("mitra", t["mitra"]), ("kontak", t["kontak"])]
        nav_html = "".join(
            f'<li><a href="{self.u(self.r(k))}"{" aria-current=page" if aktif == k else ""}>{e(n)}</a></li>' for k, n in nav)
        if indeks:
            self.sitemap.append((dict(alt), lastmod or self.today))
        rss = self.u("/en/rss.xml" if lang == "en" else "/rss.xml")
        doc = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>document.documentElement.classList.add("js")</script>
<title>{e(judul_tag)}</title>
<meta name="description" content="{e(desk)}">
<link rel="canonical" href="{e(self.abs(path))}">
{head_alt}{'' if indeks else '<meta name="robots" content="noindex">' + chr(10)}<meta property="og:site_name" content="{e(self.org)}">
<meta property="og:type" content="{tipe}">
<meta property="og:title" content="{e(judul or self.org)}">
<meta property="og:description" content="{e(desk)}">
<meta property="og:url" content="{e(self.abs(path))}">
<meta property="og:image" content="{e(og_url)}">
<meta property="og:locale" content="{t['locale']}">
<meta property="og:locale:alternate" content="{T[lainnya]['locale']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#1C1A17">
<link rel="icon" type="image/png" sizes="32x32" href="{self.u('/aset/favicon-32.png')}">
<link rel="icon" type="image/png" sizes="192x192" href="{self.u('/aset/favicon-192.png')}">
<link rel="apple-touch-icon" href="{self.u('/aset/apple-touch-icon.png')}">
<link rel="alternate" type="application/rss+xml" title="{e(self.org)} — {e(t['kabar'])}" href="{rss}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jost:wght@500;600;700&family=Nunito+Sans:ital,opsz,wght@0,6..12,400;0,6..12,600;0,6..12,700;1,6..12,400&display=swap">
<link rel="stylesheet" href="{self.url_css}">
{ld_html}</head>
<body>
<a class="lewati" href="#isi">{e(t['lewati'])}</a>
<header class="kepala">
  <div class="wadah kepala-dalam">
    <a class="merek" href="{self.u(self.r('home'))}" aria-label="{e(self.org)} — {e(t['beranda'])}">
      <img src="{self.u('/aset/logo-emas-96.png')}" width="40" height="40" alt="">
      <span class="merek-teks"><span class="merek-nama">FAJAR SIKKA</span><span class="merek-sub">{e(t['tagline_lokasi'])}</span></span>
    </a>
    <button class="tombol-menu" aria-expanded="false" aria-controls="nav-utama"><span class="garis-menu" aria-hidden="true"></span><span class="sr">{e(t['menu'])}</span></button>
    <nav id="nav-utama" class="nav" aria-label="{e(t['navigasi'])}">
      <ul>{nav_html}</ul>
      <div class="nav-aksi">
        <a class="bahasa" href="{self.u(tukar)}" hreflang="{lainnya}" lang="{lainnya}" title="{e(t['ganti_bahasa_label'])}">{T[lainnya]['lang_pendek']}</a>
        <a class="btn btn-emas btn-kecil" href="{self.u(self.r('dukung'))}"{" aria-current=page" if aktif == "dukung" else ""}>{e(t['dukung'])}</a>
      </div>
    </nav>
  </div>
</header>
<main id="isi">
{isi}
</main>
{self._kaki(tukar, lainnya)}
<script src="{self.url_js}" defer></script>
</body>
</html>
"""
        self.tulis(path, doc)

    def _kaki(self, tukar, lainnya):
        t = self.t
        th = self.today.year
        sos = []
        for k, label in (("instagram", "Instagram"), ("facebook", "Facebook")):
            if self.p(k):
                sos.append(f'<a href="{e(self.p(k))}" rel="noopener me" target="_blank">{label}</a>')
        wa = self.P.get("whatsapp", {}).get("id", "")
        kontak = []
        if self.p("email"):
            kontak.append(f'<a href="mailto:{e(self.p("email"))}">{e(self.p("email"))}</a>')
        if self.p("telepon"):
            kontak.append(f'<a href="https://wa.me/{e(wa)}" rel="noopener">{e(self.p("telepon"))}</a>' if wa else e(self.p("telepon")))
        links = [("tentang", t["tentang"]), ("program", t["program"]), ("kabar", t["kabar"]), ("galeri", t["galeri"]),
                 ("mitra", t["mitra"]), ("dukung", t["dukung"]), ("kontak", t["kontak"])]
        return f"""<footer class="kaki">
  <div class="wadah kaki-grid">
    <div class="kaki-merek">
      <img src="{self.u('/aset/logo-emas-96.png')}" width="56" height="56" alt="">
      <p class="kaki-nama">FAJAR SIKKA</p>
      <p class="kaki-motto">{e(self.p('motto'))}</p>
    </div>
    <div>
      <h2 class="kaki-judul">{e(t['navigasi'])}</h2>
      <ul class="kaki-list">{''.join(f'<li><a href="{self.u(self.r(k))}">{e(n)}</a></li>' for k, n in links)}</ul>
    </div>
    <div>
      <h2 class="kaki-judul">{e(t['hubungi_kami'])}</h2>
      <address class="kaki-alamat">{e(self.p('alamat'))}</address>
      <ul class="kaki-list">{''.join(f'<li>{k}</li>' for k in kontak + sos)}</ul>
    </div>
  </div>
  <div class="wadah kaki-bawah">
    <p>© {self.cfg.get('tahun_berdiri', 2018)}–{th} {e(self.org)}. {e(t['foto_lanskap'])}</p>
    <p><a href="{self.u(tukar)}" hreflang="{lainnya}" lang="{lainnya}">{e(t['ganti_bahasa'])}</a> · <a href="{self.u('/en/rss.xml' if self.lang == 'en' else '/rss.xml')}">{e(t['berlangganan_rss'])}</a></p>
  </div>
</footer>"""

    # ---------- komponen ----------
    def judul_bagian(self, label, judul, intro="", tag="h2", id_=None):
        i = f' id="{id_}"' if id_ else ""
        return (f'<div class="judul-bagian"><p class="label">{e(label)}</p><{tag}{i}>{e(judul)}</{tag}>'
                + (f'<p class="intro">{e(intro)}</p>' if intro else "") + "</div>")

    def hero_halaman(self, label, judul, intro, foto_key="pantai", foto=None, alt=None):
        im, a = (foto, alt) if foto else self.fl(foto_key)
        return f"""<section class="hero-hal">
  <div class="hero-hal-foto">{self.img(im, a, eager=True)}</div>
  <div class="wadah hero-hal-isi">
    <p class="label label-terang">{e(label)}</p>
    <h1>{e(judul)}</h1>
    {f'<p class="hero-hal-intro">{e(intro)}</p>' if intro else ''}
  </div>
</section>"""

    def kartu_program(self, pr, h="h3"):
        lang = self.lang
        meta = " · ".join(x for x in [pr["periode"] or (self.t["berkelanjutan"] if not pr["tahun"] else str(pr["tahun"])), pr["lokasi"]] if x)
        foto = (f'<div class="kartu-foto">{self.img(pr["foto"][0], pr["nama"][lang], "(min-width: 900px) 33vw, 100vw")}</div>'
                if pr["foto"] else "")
        return f"""<article class="kartu kartu-program{' ada-foto' if foto else ''}" data-bidang="{e(pr['bidang'] or '')}">
  {foto}
  <div class="kartu-isi">
    {f'<p class="chip">{e(self.bidang(pr["bidang"]))}</p>' if pr['bidang'] else ''}
    <{h} class="kartu-judul"><a href="{self.u(self.rd('program', pr['slug']))}">{e(pr['nama'][lang])}</a></{h}>
    <p class="kartu-meta">{e(meta)}</p>
    <p>{e(pr['ringkas'][lang] or md.excerpt(pr['desk'][lang], 140))}</p>
  </div>
</article>"""

    def kartu_artikel(self, a, h="h3"):
        lang = self.lang
        im = a["sampul"]
        if im:
            foto = self.img(im, a["alt"], "(min-width: 900px) 33vw, 100vw")
        else:
            k = ["pantai", "padar", "senja", "bukit", "airterjun"][int(hashlib.md5(a["slug"].encode()).hexdigest(), 16) % 5]
            fi, fa = self.fl(k)
            foto = self.img(fi, fa, "(min-width: 900px) 33vw, 100vw")
        kat = a["kategori"][0]["nama"][lang] if a["kategori"] else ""
        return f"""<article class="kartu kartu-artikel">
  <div class="kartu-foto">{foto}</div>
  <div class="kartu-isi">
    <p class="kartu-meta">{f'<span class="chip">{e(kat)}</span> ' if kat else ''}<time datetime="{a['tgl'].isoformat()}">{self.tgl(a['tgl'])}</time></p>
    <{h} class="kartu-judul"><a href="{self.u(self.rd('kabar', a['slug']))}">{e(a['judul'][lang])}</a></{h}>
    <p>{e(a['ringkas'][lang])}</p>
  </div>
</article>"""

    def kartu_album(self, g, h="h3"):
        lang = self.lang
        return f"""<article class="kartu kartu-album">
  <a class="kartu-foto" href="{self.u(self.rd('galeri', g['slug']))}" tabindex="-1" aria-hidden="true">{self.img(g['foto'][0], g['judul'][lang], "(min-width: 900px) 33vw, 100vw")}
    <span class="jumlah-foto">{len(g['foto'])} {e(self.t['foto'])}</span></a>
  <div class="kartu-isi">
    <p class="kartu-meta">{' · '.join(x for x in [self.tgl(g['tgl']), g['lokasi']] if x)}</p>
    <{h} class="kartu-judul"><a href="{self.u(self.rd('galeri', g['slug']))}">{e(g['judul'][lang])}</a></{h}>
  </div>
</article>"""

    def cta_dukung(self):
        t = self.t
        im, alt = self.fl("bukit")
        return f"""<section class="cta">
  <div class="cta-foto">{self.img(im, alt)}</div>
  <div class="wadah cta-isi">
    <img class="cta-logo" src="{self.u('/aset/logo-putih-96.png')}" width="64" height="64" alt="">
    <h2>{e(t['dukung_cta'])}</h2>
    <p>{e(self.p('donasi_intro'))}</p>
    <p class="aksi"><a class="btn btn-emas" href="{self.u(self.r('dukung'))}">{e(t['dukung'])}</a>
    <a class="btn btn-garis-terang" href="{self.u(self.r('kontak'))}">{e(t['hubungi_kami'])}</a></p>
  </div>
</section>"""

    def ld_org(self):
        o = {"@context": "https://schema.org", "@type": "NGO", "@id": self.abs("/#organisasi"),
             "name": self.org, "alternateName": "Komunitas Fajar Sikka", "url": self.abs("/"),
             "logo": self.abs("/aset/logo-emas.png"), "image": self.abs("/aset/og-default.jpg"),
             "foundingDate": str(self.cfg.get("tahun_berdiri", 2018)),
             "description": md.excerpt(self.P.get("hero_teks", {}).get(self.lang, ""), 300),
             "slogan": self.p("motto"),
             "address": {"@type": "PostalAddress", "streetAddress": "Jl. Nairoa, RT09/RW04, Desa Habi",
                         "addressLocality": "Kangae, Kabupaten Sikka", "addressRegion": "Nusa Tenggara Timur",
                         "addressCountry": "ID"},
             "areaServed": "Kabupaten Sikka, Flores, Nusa Tenggara Timur"}
        if self.p("email"):
            o["email"] = self.p("email")
        if self.P.get("telepon", {}).get("en"):
            o["telephone"] = self.P["telepon"]["en"]
        same = [self.p(k) for k in ("instagram", "facebook") if self.p(k)]
        if same:
            o["sameAs"] = same
        return o

    # ================= HALAMAN =================
    def hal_beranda(self):
        t, lang = self.t, self.lang
        im, alt = self.fl("padar")
        stats = []
        for baris in self.baris("angka_dampak"):
            if "|" in baris:
                n, k = baris.split("|", 1)
                stats.append(f'<li><span class="angka">{e(n.strip())}</span><span class="angka-ket">{e(k.strip())}</span></li>')
        stats_html = f'<section class="angka-wrap" aria-label="{e(t["tentang_kami"])}"><ul class="wadah angka-list">{"".join(stats)}</ul></section>' if stats else ""
        prog = "".join(self.kartu_program(p) for p in self.program[:6])
        kabar = ""
        artikel = [a for a in self.artikel if lang == "id" or a["ada_en"]][:3]
        if artikel:
            kabar = f"""<section class="bagian">
  <div class="wadah">
    <div class="bagian-kepala">{self.judul_bagian(t['kabar'], t['kabar_terbaru'])}<a class="tautan-panah" href="{self.u(self.r('kabar'))}">{e(t['lihat_semua'])}</a></div>
    <div class="grid grid-3">{''.join(self.kartu_artikel(a) for a in artikel)}</div>
  </div>
</section>"""
        if self.galeri:
            galeri = f"""<section class="bagian bagian-putih">
  <div class="wadah">
    <div class="bagian-kepala">{self.judul_bagian(t['galeri'], t['foto_kegiatan'])}<a class="tautan-panah" href="{self.u(self.r('galeri'))}">{e(t['lihat_semua'])}</a></div>
    <div class="grid grid-3">{''.join(self.kartu_album(g) for g in self.galeri[:3])}</div>
  </div>
</section>"""
        else:
            galeri = ""
        # pita lanskap Flores (pemanis)
        pita = "".join(f'<figure class="pita-item">{self.img(*self.fl(k), sizes="(min-width: 900px) 25vw, 50vw")}</figure>'
                       for k in ("pantai", "airterjun", "senja", "bukit"))
        mitra = "".join(f'<li>{e(m["nama"])}</li>' for m in self.mitra_tampil)
        motto = self.p("motto")
        isi = f"""<section class="hero">
  <div class="hero-foto">{self.img(im, alt, eager=True)}</div>
  <div class="wadah hero-isi">
    <p class="label label-terang">{e(t['tagline_lokasi'])} · {e(t['tahun_berdiri'])} {self.cfg.get('tahun_berdiri', 2018)}</p>
    <h1>{e(self.p('hero_judul'))}</h1>
    <p class="hero-teks">{e(self.p('hero_teks'))}</p>
    <p class="aksi"><a class="btn btn-emas" href="{self.u(self.r('tentang'))}">{e(t['kenali'])}</a>
      <a class="btn btn-garis-terang" href="{self.u(self.r('dukung'))}">{e(t['dukung'])}</a></p>
  </div>
</section>
{stats_html}
<section class="bagian">
  <div class="wadah dua-kolom">
    <div>
      {self.judul_bagian(t['tentang_kami'], self.p('visi'))}
      {self.paragraf(self.p('tentang_singkat'))}
      <p><a class="tautan-panah" href="{self.u(self.r('tentang'))}">{e(t['selengkapnya'])}</a></p>
    </div>
    <figure class="motto-kartu">
      <img class="motto-logo" src="{self.u('/aset/logo-emas.png')}" width="120" height="120" alt="Logo {e(self.org)}">
      <blockquote>“{e(motto.rstrip('.'))}.”</blockquote>
      <figcaption>{e(t['motto'])} {e(self.org)}</figcaption>
    </figure>
  </div>
</section>
<section class="bagian bagian-putih">
  <div class="wadah">
    <div class="bagian-kepala">{self.judul_bagian(t['program'], t['program_kami'], t['program_intro'])}<a class="tautan-panah" href="{self.u(self.r('program'))}">{e(t['lihat_semua'])}</a></div>
    <div class="grid grid-3">{prog}</div>
  </div>
</section>
{kabar}
{galeri}
<section class="pita" aria-label="Flores">{pita}</section>
<section class="bagian bagian-mitra">
  <div class="wadah">
    <div class="bagian-kepala">{self.judul_bagian(t['mitra'], t['jejaring'])}<a class="tautan-panah" href="{self.u(self.r('mitra'))}">{e(t['lihat_semua'])}</a></div>
    <ul class="mitra-pita">{mitra}</ul>
  </div>
</section>
{self.cta_dukung()}"""
        ld = [self.ld_org(), {"@context": "https://schema.org", "@type": "WebSite", "name": self.org,
                              "url": self.abs(self.r("home")), "inLanguage": lang,
                              "publisher": {"@id": self.abs("/#organisasi")}}]
        judul = f"{self.org} — {self.p('hero_judul').rstrip('.')}"
        self.halaman(self.r("home"), "", md.excerpt(self.p("hero_teks"), 158), isi, alt=dict(RUTE["home"]),
                     og="/aset/og-default.jpg", ld=ld, aktif="home", judul_penuh=judul)

    def hal_tentang(self):
        t, lang = self.t, self.lang
        misi = "".join(f"<li>{e(x)}</li>" for x in self.baris("misi"))
        tujuan = "".join(f"<li>{e(x)}</li>" for x in self.baris("tujuan"))
        logo = "".join(f"<li>{e(x)}</li>" for x in LOGO[lang])

        def orang(p):
            ft = (f'<div class="orang-foto">{self.img(p["foto"], p["nama"], "160px")}</div>' if p["foto"]
                  else f'<div class="orang-foto orang-inisial" aria-hidden="true">{e("".join(w[0] for w in p["nama"].split()[:2]).upper())}</div>')
            return f'<li class="orang">{ft}<p class="orang-nama">{e(p["nama"])}</p><p class="orang-jabatan">{e(p["jabatan"][lang])}</p></li>'
        kelompok = [("Pengurus Inti", t["pengurus"]), ("Ketua Bidang", t["ketua_bidang"]), ("Penasehat", t["penasehat"])]
        tim = ""
        for kode, label in kelompok:
            orang_ = [p for p in self.pengurus if p["kelompok"] == kode]
            if orang_:
                tim += f'<h3 class="sub-judul">{e(label)}</h3><ul class="orang-grid">{"".join(orang(p) for p in orang_)}</ul>'
        isi = f"""{self.hero_halaman(t['tentang_kami'], self.org, self.p('hero_judul'), 'pantai')}
<section class="bagian">
  <div class="wadah prosa-wadah">
    <div class="prosa">
      <h2>{e(t['latar_belakang'])}</h2>
      {self.paragraf(self.p('latar_belakang'))}
      <h2>{e(t['makna_nama'])}</h2>
      {self.paragraf(self.p('makna_nama'))}
    </div>
  </div>
</section>
<section class="bagian bagian-gelap">
  <div class="wadah">
    <div class="visi">
      <p class="label">{e(t['visi'])}</p>
      <p class="visi-teks">{e(self.p('visi'))}</p>
    </div>
    <div class="grid grid-2 vm">
      <div><h2 class="sub-judul-terang">{e(t['misi'])}</h2><ol class="daftar-angka">{misi}</ol></div>
      <div><h2 class="sub-judul-terang">{e(t['tujuan'])}</h2><ol class="daftar-angka">{tujuan}</ol>
        <h2 class="sub-judul-terang">{e(t['sasaran'])}</h2><p>{e(self.p('sasaran'))}</p></div>
    </div>
    <p class="motto-baris"><span>{e(t['motto'])}</span> “{e(self.p('motto').rstrip('.'))}.”</p>
  </div>
</section>
<section class="bagian">
  <div class="wadah logo-makna">
    <img src="{self.u('/aset/logo-emas.png')}" width="280" height="280" alt="Logo {e(self.org)}" loading="lazy">
    <div>{self.judul_bagian(t['tentang_kami'], t['makna_logo'])}<ol class="daftar-logo">{logo}</ol></div>
  </div>
</section>
{f'<section class="bagian bagian-putih"><div class="wadah">{self.judul_bagian(t["tentang_kami"], t["pengurus"])}{tim}</div></section>' if tim else ''}
{self.cta_dukung()}"""
        self.halaman(self.r("tentang"), t["tentang_kami"], md.excerpt(self.p("latar_belakang"), 158), isi,
                     alt=dict(RUTE["tentang"]), og=self.fl("pantai")[0].og, ld=[self.ld_org()], aktif="tentang",
                     remah=[(t["tentang_kami"], self.r("tentang"))])

    def hal_program(self):
        t, lang = self.t, self.lang
        bidang = sorted({p["bidang"] for p in self.program if p["bidang"]})
        chips = (f'<div class="saring" role="group" aria-label="{e(t["bidang"])}" hidden>'
                 f'<button type="button" class="chip-btn" aria-pressed="true" data-saring="">{e(t["semua"])}</button>'
                 + "".join(f'<button type="button" class="chip-btn" aria-pressed="false" data-saring="{e(b)}">{e(self.bidang(b))}</button>' for b in bidang)
                 + "</div>")
        isi = f"""{self.hero_halaman(t['program'], t['program_kami'], t['program_intro'], 'senja')}
<section class="bagian">
  <div class="wadah">
    {chips}
    <div class="grid grid-3" data-daftar-saring>{''.join(self.kartu_program(p, 'h2') for p in self.program)}</div>
  </div>
</section>
{self.cta_dukung()}"""
        ld = [{"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": self.abs(self.rd("program", p["slug"])), "name": p["nama"][lang]}
            for i, p in enumerate(self.program)]}]
        self.halaman(self.r("program"), t["program_kami"], t["program_intro"], isi, alt=dict(RUTE["program"]),
                     og=self.fl("senja")[0].og, ld=ld, aktif="program", remah=[(t["program"], self.r("program"))])
        for i, pr in enumerate(self.program):
            self._detail_program(pr, i)

    def _detail_program(self, pr, i):
        t, lang = self.t, self.lang
        path = self.rd("program", pr["slug"])
        foto = pr["foto"][0] if pr["foto"] else None
        meta = []
        meta.append((t["periode"], pr["periode"] or (str(pr["tahun"]) if pr["tahun"] else t["berkelanjutan"])))
        if pr["lokasi"]:
            meta.append((t["lokasi"], pr["lokasi"]))
        if pr["bidang"]:
            meta.append((t["bidang"], self.bidang(pr["bidang"])))
        if pr["mitra"]:
            meta.append((t["bersama"], ", ".join(m["nama"] for m in pr["mitra"])))
        meta_html = "".join(f"<div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>" for k, v in meta)
        galeri = ""
        if len(pr["foto"]) > 1:
            galeri = self._grid_foto(pr["foto"][1:], pr["nama"][lang])
        album = ""
        if pr["album"]:
            album = f'<h2 class="sub-judul">{e(t["album_terkait"])}</h2><div class="grid grid-3">{"".join(self.kartu_album(g) for g in pr["album"])}</div>'
        lain = [p for p in self.program if p is not pr and p["bidang"] == pr["bidang"]][:3] or \
               [p for p in self.program if p is not pr][:3]
        lang_attr = ' lang="id"' if lang == "en" and pr["desk"]["en"] == pr["desk"]["id"] and pr["desk"]["id"] else ""
        isi = f"""{self.hero_halaman(self.bidang(pr['bidang']) or t['program'], pr['nama'][lang], pr['ringkas'][lang], 'senja', foto, pr['nama'][lang])}
<section class="bagian">
  <div class="wadah prosa-wadah">
    <dl class="meta-daftar">{meta_html}</dl>
    <div class="prosa"{lang_attr}>{md.render(pr['desk'][lang])}</div>
    {galeri}
    {album}
  </div>
</section>
<section class="bagian bagian-putih">
  <div class="wadah">
    <div class="bagian-kepala">{self.judul_bagian(t['program'], t['program_lain'])}<a class="tautan-panah" href="{self.u(self.r('program'))}">{e(t['lihat_semua'])}</a></div>
    <div class="grid grid-3">{''.join(self.kartu_program(p) for p in lain)}</div>
  </div>
</section>"""
        desk = pr["ringkas"][lang] or md.excerpt(pr["desk"][lang])
        ld = [{"@context": "https://schema.org", "@type": "CreativeWork", "name": pr["nama"][lang], "description": desk,
               "url": self.abs(path), "inLanguage": lang, "author": {"@id": self.abs("/#organisasi")},
               "contributor": [{"@type": "Organization", "name": m["nama"]} for m in pr["mitra"]] or None,
               "locationCreated": {"@type": "Place", "name": pr["lokasi"]} if pr["lokasi"] else None}]
        ld[0] = {k: v for k, v in ld[0].items() if v}
        self.halaman(path, pr["nama"][lang], desk, isi,
                     alt={l: self.rd("program", pr["slug"], l) for l in LANGS},
                     og=(foto.og if foto else self.fl("senja")[0].og), ld=ld, aktif="program",
                     remah=[(t["program"], self.r("program")), (pr["nama"][lang], path)])

    def _grid_foto(self, fotos, judul, tipe="kecil"):
        items = []
        for i, f in enumerate(fotos):
            alt = f"{judul} — {self.t['foto']} {i + 1}"
            items.append(f'<li><a href="{f.src}" class="foto-link" data-lightbox data-w="{f.w}" data-h="{f.h}" '
                         f'data-srcset="{e(f.srcset)}">{self.img(f, alt, "(min-width: 900px) 25vw, 50vw")}</a></li>')
        return f'<ul class="grid-foto grid-foto-{tipe}">{"".join(items)}</ul>'

    def hal_kabar(self):
        t, lang = self.t, self.lang
        daftar = [a for a in self.artikel if lang == "id" or a["ada_en"]]
        n_hal = max(1, -(-len(daftar) // PER_HALAMAN))
        for h in range(1, n_hal + 1):
            potong = daftar[(h - 1) * PER_HALAMAN: h * PER_HALAMAN]
            path = self.r("kabar") if h == 1 else self.rd("halaman", h)
            if potong:
                grid = f'<div class="grid grid-3">{"".join(self.kartu_artikel(a, "h2") for a in potong)}</div>'
            else:
                extra = (f' <a href="{self.u(RUTE["kabar"]["id"])}" hreflang="id">{e(t["hanya_id"])} →</a>'
                         if lang == "en" and self.artikel else "")
                grid = f'<p class="kosong">{e(t["belum_ada_kabar"])}{extra}</p>'
            nav = ""
            if n_hal > 1:
                items = []
                for j in range(1, n_hal + 1):
                    pj = self.r("kabar") if j == 1 else self.rd("halaman", j)
                    items.append(f'<li><a href="{self.u(pj)}"{" aria-current=page" if j == h else ""}>{j}</a></li>')
                nav = f'<nav class="paginasi" aria-label="{e(t["halaman"])}"><ul>{"".join(items)}</ul></nav>'
            kat = [k for k in self.kategori.values() if any(lang == "id" or a["ada_en"] for a in k["artikel"])]
            kat_html = ""
            if kat:
                kat_html = ('<div class="saring">' + f'<a class="chip-btn" aria-current="page" href="{self.u(self.r("kabar"))}">{e(t["semua"])}</a>'
                            + "".join(f'<a class="chip-btn" href="{self.u(self.rd("kategori", k["slug"]))}">{e(k["nama"][lang])}</a>' for k in kat)
                            + "</div>")
            isi = f"""{self.hero_halaman(t['kabar'], t['kabar_terbaru'], t['kabar_intro'], 'airterjun')}
<section class="bagian"><div class="wadah">{kat_html}{grid}{nav}</div></section>"""
            judul = t["kabar_terbaru"] + (f" — {t['halaman']} {h}" if h > 1 else "")
            alt = dict(RUTE["kabar"]) if h == 1 else {lang: path}
            self.halaman(path, judul, t["kabar_intro"], isi, alt=alt, og=self.fl("airterjun")[0].og, aktif="kabar",
                         remah=[(t["kabar"], self.r("kabar"))], lastmod=potong[0]["tgl"] if potong else None)
        # kategori
        for k in self.kategori.values():
            arts = [a for a in k["artikel"] if lang == "id" or a["ada_en"]]
            if not arts:
                continue
            path = self.rd("kategori", k["slug"])
            isi = f"""{self.hero_halaman(t['kategori'], k['nama'][lang], '', 'airterjun')}
<section class="bagian"><div class="wadah"><div class="grid grid-3">{''.join(self.kartu_artikel(a, 'h2') for a in arts)}</div></div></section>"""
            alt = {l: self.rd("kategori", k["slug"], l) for l in LANGS
                   if l == lang or any(l == "id" or a["ada_en"] for a in k["artikel"])}
            self.halaman(path, k["nama"][lang], f"{t['kabar']}: {k['nama'][lang]} — {self.org}", isi, alt=alt,
                         aktif="kabar", remah=[(t["kabar"], self.r("kabar")), (k["nama"][lang], path)])
        for i, a in enumerate(daftar):
            self._detail_artikel(a, daftar, i)

    def _detail_artikel(self, a, daftar, i):
        t, lang = self.t, self.lang
        path = self.rd("kabar", a["slug"])
        fotos = a["foto"]

        def sisip(n):
            if 1 <= n <= len(fotos) and fotos[n - 1]:
                f = fotos[n - 1]
                return (f'<figure class="foto-artikel"><a href="{f.src}" data-lightbox data-srcset="{e(f.srcset)}">'
                        f'{self.img(f, a["judul"][lang] + " — " + t["foto"] + " " + str(n), "(min-width: 800px) 760px, 100vw")}</a></figure>')
            return ""
        body = md.render(a["isi"][lang], sisip)
        dipakai = set(int(x) for x in re.findall(r"\[foto\s*:\s*(\d+)\s*\]", a["isi"][lang] or "", re.I))
        sisa = [f for j, f in enumerate(fotos, 1) if f and j not in dipakai]
        if sisa:
            body += self._grid_foto(sisa, a["judul"][lang])
        url_abs = self.abs(path)
        judul = a["judul"][lang]
        q = urllib.parse.quote
        share = f"""<div class="bagikan"><span>{e(t['bagikan'])}</span>
  <a href="https://wa.me/?text={q(judul + ' ' + url_abs)}" rel="noopener" target="_blank">WhatsApp</a>
  <a href="https://www.facebook.com/sharer/sharer.php?u={q(url_abs)}" rel="noopener" target="_blank">Facebook</a>
  <a href="https://x.com/intent/post?url={q(url_abs)}&amp;text={q(judul)}" rel="noopener" target="_blank">X</a>
  <button type="button" data-salin="{e(url_abs)}" data-tersalin="{e(t['tersalin'])}">{e(t['salin_tautan'])}</button></div>"""
        kat = " ".join(f'<a class="chip" href="{self.u(self.rd("kategori", k["slug"]))}">{e(k["nama"][lang])}</a>' for k in a["kategori"])
        sampul = ""
        if a["sampul"]:
            sampul = f'<figure class="sampul">{self.img(a["sampul"], a["alt"], "(min-width: 1000px) 1000px, 100vw", eager=True)}</figure>'
        lain = [x for x in daftar if x is not a][:3]
        isi = f"""<article class="artikel">
  <header class="artikel-kepala wadah">
    <p class="kartu-meta">{kat} <time datetime="{a['tgl'].isoformat()}">{self.tgl(a['tgl'])}</time>{f" · {e(t['oleh'])} {e(a['penulis'])}" if a['penulis'] else ''}</p>
    <h1>{e(judul)}</h1>
    <p class="artikel-ringkas">{e(a['ringkas'][lang])}</p>
  </header>
  <div class="wadah">{sampul}</div>
  <div class="wadah prosa-wadah"><div class="prosa">{body}</div>{share}</div>
</article>
{f'<section class="bagian bagian-putih"><div class="wadah"><div class="bagian-kepala">{self.judul_bagian(t["kabar"], t["artikel_lain"])}</div><div class="grid grid-3">{"".join(self.kartu_artikel(x) for x in lain)}</div></div></section>' if lain else ''}"""
        desk = a["seo_desk"] if (a["seo_desk"] and lang == "id") else a["ringkas"][lang]
        judul_seo = a["seo_judul"] if (a["seo_judul"] and lang == "id") else judul
        og = a["sampul"].og if a["sampul"] else None
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": judul[:110], "description": desk,
               "datePublished": a["tgl"].isoformat(), "inLanguage": lang, "mainEntityOfPage": url_abs,
               "image": [self.abs(og or "/aset/og-default.jpg")],
               "author": ({"@type": "Person", "name": a["penulis"]} if a["penulis"] else {"@id": self.abs("/#organisasi")}),
               "publisher": {"@type": "Organization", "name": self.org, "logo": {"@type": "ImageObject", "url": self.abs("/aset/logo-emas.png")}}}]
        alt = {"id": self.rd("kabar", a["slug"], "id")}
        if a["ada_en"]:
            alt["en"] = self.rd("kabar", a["slug"], "en")
        self.halaman(path, judul_seo, desk, isi, alt=alt, og=og, tipe="article", ld=ld, aktif="kabar",
                     lastmod=a["tgl"], remah=[(t["kabar"], self.r("kabar")), (judul, path)])

    def hal_galeri(self):
        t, lang = self.t, self.lang
        if self.galeri:
            grid = f'<div class="grid grid-3">{"".join(self.kartu_album(g, "h2") for g in self.galeri)}</div>'
        else:
            pita = "".join(f'<li>{self.img(*self.fl(k), sizes="(min-width: 900px) 33vw, 50vw")}</li>' for k in ("pantai", "padar", "airterjun", "senja", "bukit"))
            grid = f'<p class="kosong">{e(t["belum_ada_galeri"])}</p><ul class="grid-foto grid-foto-lanskap">{pita}</ul>'
        isi = f"""{self.hero_halaman(t['galeri'], t['foto_kegiatan'], t['galeri_intro'], 'bukit')}
<section class="bagian"><div class="wadah">{grid}</div></section>"""
        self.halaman(self.r("galeri"), t["foto_kegiatan"], t["galeri_intro"], isi, alt=dict(RUTE["galeri"]),
                     og=self.fl("bukit")[0].og, aktif="galeri", remah=[(t["galeri"], self.r("galeri"))])
        for g in self.galeri:
            path = self.rd("galeri", g["slug"])
            prog = ""
            if g["program"]:
                prog = " · ".join(f'<a href="{self.u(self.rd("program", p["slug"]))}">{e(p["nama"][lang])}</a>' for p in g["program"])
                prog = f'<p class="kartu-meta">{e(t["program"])}: {prog}</p>'
            isi = f"""<section class="bagian">
  <div class="wadah">
    <p class="label"><a href="{self.u(self.r('galeri'))}">{e(t['galeri'])}</a></p>
    <h1 class="judul-album">{e(g['judul'][lang])}</h1>
    <p class="kartu-meta">{' · '.join(x for x in [self.tgl(g['tgl']), g['lokasi'], f"{len(g['foto'])} {t['foto']}"] if x)}</p>
    {prog}
    {f'<div class="prosa">{self.paragraf(g["ket"][lang])}</div>' if g['ket'][lang] else ''}
    {self._grid_foto(g['foto'], g['judul'][lang], 'album')}
  </div>
</section>"""
            desk = md.excerpt(g["ket"][lang]) or f"{g['judul'][lang]} — {t['foto_kegiatan']} {self.org}"
            ld = [{"@context": "https://schema.org", "@type": "ImageGallery", "name": g["judul"][lang], "description": desk,
                   "url": self.abs(path), "inLanguage": lang,
                   "image": [self.abs(f.src) if not f.src.startswith("http") else f.src for f in g["foto"][:20]]}]
            if g["tgl"]:
                ld[0]["dateCreated"] = g["tgl"].isoformat()
            self.halaman(path, g["judul"][lang], desk, isi, alt={l: self.rd("galeri", g["slug"], l) for l in LANGS},
                         og=g["foto"][0].og, ld=ld, aktif="galeri", lastmod=g["tgl"],
                         remah=[(t["galeri"], self.r("galeri")), (g["judul"][lang], path)])

    def hal_mitra(self):
        t, lang = self.t, self.lang
        items = []
        for m in self.mitra_tampil:
            logo = f'<div class="mitra-logo">{self.img(m["logo"], "Logo " + m["nama"], "160px")}</div>' if m["logo"] else ""
            nama = f'<a href="{e(m["web"])}" rel="noopener" target="_blank">{e(m["nama"])}</a>' if m["web"] else e(m["nama"])
            items.append(f'<li class="kartu mitra-kartu">{logo}<div class="kartu-isi"><h2 class="kartu-judul">{nama}</h2><p>{e(m["kerja"][lang])}</p></div></li>')
        isi = f"""{self.hero_halaman(t['mitra'], t['jejaring'], t['mitra_intro'], 'padar')}
<section class="bagian"><div class="wadah"><ul class="grid grid-3 mitra-grid">{''.join(items)}</ul></div></section>
{self.cta_dukung()}"""
        self.halaman(self.r("mitra"), t["jejaring"], t["mitra_intro"], isi, alt=dict(RUTE["mitra"]),
                     og=self.fl("padar")[0].og, aktif="mitra", remah=[(t["mitra"], self.r("mitra"))])

    def _tombol_kontak(self, subjek=""):
        t = self.t
        out = []
        if self.p("email"):
            s = f"?subject={urllib.parse.quote(subjek)}" if subjek else ""
            out.append(f'<a class="btn btn-emas" href="mailto:{e(self.p("email"))}{s}">{e(t["kirim_email"])}</a>')
        wa = self.P.get("whatsapp", {}).get("id", "")
        if wa:
            txt = f"?text={urllib.parse.quote(subjek)}" if subjek else ""
            out.append(f'<a class="btn btn-garis" href="https://wa.me/{e(wa)}{txt}" rel="noopener">{e(t["chat_wa"])}</a>')
        return f'<p class="aksi">{"".join(out)}</p>' if out else ""

    def hal_dukung(self):
        t, lang = self.t, self.lang
        bank, norek, an = (self.P.get(k, {}).get("id", "") for k in ("rekening_bank", "rekening_nomor", "rekening_nama"))
        if bank and norek:
            donasi = f"""<div class="kartu kartu-donasi">
  <div class="kartu-isi">
    <h2>{e(t['donasi_rekening'])}</h2>
    <dl class="rekening">
      <div><dt>{e(t['bank'])}</dt><dd>{e(bank)}</dd></div>
      <div><dt>{e(t['no_rek'])}</dt><dd><span class="norek">{e(norek)}</span> <button type="button" class="btn-salin" data-salin="{e(re.sub(r'[^0-9]', '', norek))}" data-tersalin="✓">{e(t['salin'])}</button></dd></div>
      {f"<div><dt>{e(t['atas_nama'])}</dt><dd>{e(an)}</dd></div>" if an else ''}
    </dl>
    <p class="catatan">{e(t['donasi_konfirmasi'])}</p>
    {self._tombol_kontak(t['donasi_subjek'])}
  </div>
</div>"""
        else:
            donasi = f"""<div class="kartu kartu-donasi">
  <div class="kartu-isi">
    <h2>{e(t['donasi_email_judul'])}</h2>
    <p>{e(t['donasi_email'])}</p>
    {f'<p class="email-besar"><a href="mailto:{e(self.p("email"))}?subject={urllib.parse.quote(t["donasi_subjek"])}">{e(self.p("email"))}</a></p>' if self.p('email') else ''}
    {self._tombol_kontak(t['donasi_subjek'])}
  </div>
</div>"""
        cara = "".join(f"<li>{e(x)}</li>" for x in self.baris("donasi_cara_lain"))
        isi = f"""{self.hero_halaman(t['dukung'], t['dukung_judul'], t['dukung_cta'], 'bukit')}
<section class="bagian">
  <div class="wadah dua-kolom dua-kolom-atas">
    <div class="prosa">{self.paragraf(self.p('donasi_intro'))}
      {f'<h2>{e(t["cara_lain"])}</h2><ul class="daftar-cek">{cara}</ul>' if cara else ''}
    </div>
    {donasi}
  </div>
</section>"""
        self.halaman(self.r("dukung"), t["dukung_judul"], md.excerpt(self.p("donasi_intro"), 158), isi,
                     alt=dict(RUTE["dukung"]), og=self.fl("bukit")[0].og, aktif="dukung",
                     remah=[(t["dukung"], self.r("dukung"))])

    def hal_kontak(self):
        t, lang = self.t, self.lang
        wa = self.P.get("whatsapp", {}).get("id", "")
        baris = [(t["alamat"], f'<address>{e(self.p("alamat"))}</address><a class="tautan-panah" href="https://www.google.com/maps/search/?api=1&amp;query={urllib.parse.quote("Desa Habi, Kangae, Sikka, Nusa Tenggara Timur")}" rel="noopener" target="_blank">{e(t["buka_peta"])}</a>')]
        if self.p("telepon"):
            baris.append((t["telepon"], f'<a href="tel:+{e(wa)}">{e(self.p("telepon"))}</a>' if wa else e(self.p("telepon"))))
        if self.p("email"):
            baris.append((t["email"], f'<a href="mailto:{e(self.p("email"))}">{e(self.p("email"))}</a>'))
        sos = [f'<a href="{e(self.p(k))}" rel="noopener me" target="_blank">{n}</a>' for k, n in (("instagram", "Instagram"), ("facebook", "Facebook")) if self.p(k)]
        if sos:
            baris.append((t["media_sosial"], " · ".join(sos)))
        info = "".join(f"<div><dt>{e(k)}</dt><dd>{v}</dd></div>" for k, v in baris)
        form = self.P.get("formulir_kontak", {}).get("id", "")
        form_html = ""
        if form.startswith("https://airtable.com/"):
            emb = form if "/embed/" in form else form.replace("https://airtable.com/", "https://airtable.com/embed/")
            form_html = f'<div class="bagian-form"><h2 class="sub-judul">{e(t["formulir"])}</h2><iframe class="form-airtable" src="{e(emb)}" title="{e(t["formulir"])}" loading="lazy"></iframe></div>'
        isi = f"""{self.hero_halaman(t['kontak'], t['hubungi_kami'], t['kontak_intro'], 'airterjun')}
<section class="bagian">
  <div class="wadah dua-kolom dua-kolom-atas">
    <dl class="kontak-daftar">{info}</dl>
    <div class="kartu kartu-donasi"><div class="kartu-isi"><h2>{e(t['hubungi_kami'])}</h2><p>{e(t['kontak_intro'])}</p>{self._tombol_kontak()}</div></div>
  </div>
  <div class="wadah">{form_html}</div>
</section>"""
        ld = [dict(self.ld_org(), **{"@type": "NGO"}), {"@context": "https://schema.org", "@type": "ContactPage",
                                                       "url": self.abs(self.r("kontak")), "inLanguage": lang}]
        self.halaman(self.r("kontak"), t["hubungi_kami"], t["kontak_intro"], isi, alt=dict(RUTE["kontak"]),
                     og=self.fl("airterjun")[0].og, ld=ld, aktif="kontak", remah=[(t["kontak"], self.r("kontak"))])

    def hal_404(self):
        t = self.t
        im, alt = self.fl("senja")
        isi = f"""<section class="hero hero-404">
  <div class="hero-foto">{self.img(im, alt, eager=True)}</div>
  <div class="wadah hero-isi">
    <p class="label label-terang">404</p>
    <h1>{e(t['halaman_tidak_ada'])}</h1>
    <p class="hero-teks">{e(t['halaman_tidak_ada_teks'])} <span lang="en">{e(T['en']['halaman_tidak_ada_teks'])}</span></p>
    <p class="aksi"><a class="btn btn-emas" href="{self.u('/')}">{e(t['kembali_beranda'])}</a>
    <a class="btn btn-garis-terang" href="{self.u('/en/')}" lang="en">{e(T['en']['kembali_beranda'])}</a></p>
  </div>
</section>"""
        self.halaman("/404.html", t["halaman_tidak_ada"], t["halaman_tidak_ada_teks"], isi, indeks=False)

    # ---------- RSS, sitemap, robots, CNAME ----------
    def rss(self):
        t, lang = self.t, self.lang
        arts = [a for a in self.artikel if lang == "id" or a["ada_en"]][:30]
        items = "".join(f"""<item><title>{e(a['judul'][lang])}</title><link>{e(self.abs(self.rd('kabar', a['slug'])))}</link>
<guid isPermaLink="true">{e(self.abs(self.rd('kabar', a['slug'])))}</guid><pubDate>{dt.datetime.combine(a['tgl'], dt.time(8)).strftime('%a, %d %b %Y %H:%M:%S +0800')}</pubDate>
<description>{e(a['ringkas'][lang])}</description></item>""" for a in arts)
        path = "/en/rss.xml" if lang == "en" else "/rss.xml"
        self.tulis(path, f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>{e(self.org)} — {e(t['kabar'])}</title><link>{e(self.abs(self.r('kabar')))}</link>
<atom:link href="{e(self.abs(path))}" rel="self" type="application/rss+xml"/>
<description>{e(t['kabar_intro'])}</description><language>{lang}</language>
{items}
</channel></rss>
""")

    def berkas_seo(self):
        rows = []
        for alt, lastmod in self.sitemap:
            for lang, path in alt.items():
                links = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{e(self.abs(p))}"/>' for l, p in alt.items()) if len(alt) > 1 else ""
                rows.append(f"<url><loc>{e(self.abs(path))}</loc><lastmod>{lastmod.isoformat()}</lastmod>{links}</url>")
        # buang duplikat (halaman yang didaftarkan dari kedua bahasa)
        rows = list(dict.fromkeys(rows))
        self.tulis("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                   'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(rows) + "\n</urlset>\n")
        self.tulis("/robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {self.abs('/sitemap.xml')}\n")
        if self.host and not self.host.endswith("github.io") and not self.host.startswith("localhost"):
            self.tulis("/CNAME", self.host + "\n")
        self.sitemap = [s for s in self.sitemap]
