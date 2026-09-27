"""Unduh & optimalkan foto.

URL lampiran Airtable kedaluwarsa setelah beberapa jam, jadi setiap foto
diunduh saat build, diubah ke WebP dalam beberapa ukuran, lalu ikut
diterbitkan bersama website. Hasilnya disimpan di folder .cache agar build
berikutnya tidak mengunduh/memproses ulang foto yang sama.
"""
import hashlib
import os
import shutil
import urllib.request

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 80_000_000
LEBAR = [480, 800, 1200, 1800, 2200]
VERSI = "v1"  # ubah jika aturan pemrosesan berubah agar cache diperbarui


class Img:
    def __init__(self, src, srcset, w, h, og=None, alpha=False):
        self.src, self.srcset, self.w, self.h, self.og, self.alpha = src, srcset, w, h, og, alpha


class Media:
    def __init__(self, dist, cache, url):
        self.dist = os.path.join(dist, "media")
        self.cache = cache
        self.url = url  # fungsi path -> url relatif situs
        os.makedirs(self.dist, exist_ok=True)
        os.makedirs(os.path.join(cache, "asli"), exist_ok=True)
        os.makedirs(os.path.join(cache, "olah"), exist_ok=True)
        self._memo = {}
        self.gagal = []

    # ---------- sumber ----------
    def dari_lampiran(self, att, og=False):
        """att: objek lampiran Airtable {id, url, filename, type, ...}."""
        if not att or not str(att.get("type", "image/")).startswith("image/"):
            return None
        if att.get("type") in ("image/heic", "image/heif"):
            self.gagal.append(f"{att.get('filename')} (format HEIC tidak didukung — unggah sebagai JPG)")
            return None
        aid = att.get("id") or hashlib.sha1(att["url"].encode()).hexdigest()[:12]
        ext = os.path.splitext(att.get("filename") or "")[1].lower() or ".jpg"
        asli = os.path.join(self.cache, "asli", aid + ext)
        if not os.path.exists(asli):
            try:
                req = urllib.request.Request(att["url"], headers={"User-Agent": "fajarsikka-build"})
                with urllib.request.urlopen(req, timeout=120) as r, open(asli + ".part", "wb") as f:
                    shutil.copyfileobj(r, f)
                os.replace(asli + ".part", asli)
            except Exception as e:  # jangan hentikan build karena satu foto
                self.gagal.append(f"{att.get('filename')} ({e})")
                return None
        nama = _slug(os.path.splitext(att.get("filename") or "foto")[0])[:40] or "foto"
        return self._olah(asli, f"{nama}-{aid[-6:].lower()}", og)

    def dari_file(self, path, key, og=False):
        return self._olah(path, key, og)

    # ---------- pemrosesan ----------
    def _olah(self, path, key, og):
        memo_key = (key, og)
        if memo_key in self._memo:
            return self._memo[memo_key]
        try:
            im = Image.open(path)
            im = ImageOps.exif_transpose(im)
        except Exception as e:
            self.gagal.append(f"{os.path.basename(path)} ({e})")
            return None
        alpha = im.mode in ("RGBA", "LA", "P") and _ada_transparan(im)
        im = im.convert("RGBA" if alpha else "RGB")
        W, H = im.size
        lebar = [w for w in LEBAR if w < W] + [min(W, LEBAR[-1])]
        lebar = sorted(set(lebar))
        srcset = []
        for w in lebar:
            nama = f"{key}-{w}.webp"
            self._buat(nama, lambda w=w: _resize(im, w), lambda img, p: img.save(p, "WEBP", quality=80, method=5))
            srcset.append((self.url(f"/media/{nama}"), w))
        utama = next((s for s, w in srcset if w >= 1200), srcset[-1][0])
        og_url = None
        if og:
            nama = f"{key}-og.jpg"
            self._buat(nama, lambda: _crop(im.convert("RGB"), 1200, 630),
                       lambda img, p: img.save(p, "JPEG", quality=82, optimize=True, progressive=True))
            og_url = f"/media/{nama}"
        h = round(H * lebar[-1] / W)
        res = Img(utama, ", ".join(f"{s} {w}w" for s, w in srcset), lebar[-1], h, og_url, alpha)
        self._memo[memo_key] = res
        return res

    def _buat(self, nama, make, save):
        tujuan = os.path.join(self.dist, nama)
        cache = os.path.join(self.cache, "olah", VERSI + "-" + nama)
        if not os.path.exists(cache):
            img = make()
            save(img, cache + ".part")
            os.replace(cache + ".part", cache)
        if not os.path.exists(tujuan):
            shutil.copyfile(cache, tujuan)


def _ada_transparan(im):
    try:
        return im.convert("RGBA").getextrema()[3][0] < 250
    except Exception:
        return False


def _resize(im, w):
    if im.width <= w:
        return im
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def _crop(im, w, h):
    r = w / h
    W, H = im.size
    if W / H > r:
        nw = int(H * r)
        im = im.crop(((W - nw) // 2, 0, (W - nw) // 2 + nw, H))
    else:
        nh = int(W / r)
        top = max(0, int((H - nh) * 0.4))
        im = im.crop((0, top, W, top + nh))
    return im.resize((w, h), Image.LANCZOS)


def _slug(s):
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
