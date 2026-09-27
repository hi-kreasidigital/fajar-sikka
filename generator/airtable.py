"""Mengambil konten dari Airtable (atau dari data/contoh.json bila token belum ada)."""
import json
import os
import time
import urllib.parse
import urllib.request

TABEL = ["Pengaturan", "Kategori", "Mitra", "Program", "Pengurus", "Artikel", "Galeri"]
API = "https://api.airtable.com/v0"


def _get(url, token, tries=4):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:  # batas 5 permintaan/detik
                time.sleep(31)
                continue
            body = e.read().decode("utf-8", "replace")[:300]
            raise SystemExit(f"Gagal membaca Airtable ({e.code}): {body}\n"
                             "Periksa AIRTABLE_TOKEN dan airtable_base_id di site.config.json.")
        except urllib.error.URLError:
            if i < tries - 1:
                time.sleep(3 * (i + 1))
                continue
            raise


def ambil_tabel(base_id, tabel, token):
    rows, offset = [], None
    while True:
        q = {"pageSize": "100"}
        if offset:
            q["offset"] = offset
        url = f"{API}/{base_id}/{urllib.parse.quote(tabel)}?{urllib.parse.urlencode(q)}"
        data = _get(url, token)
        rows += [{"id": r["id"], "fields": r.get("fields", {})} for r in data.get("records", [])]
        offset = data.get("offset")
        time.sleep(0.25)
        if not offset:
            return rows


def ambil_semua(base_id, token, root):
    """Kembalikan (data, sumber). Satu build memakai ±7 panggilan API."""
    if token and base_id:
        data = {}
        for t in TABEL:
            try:
                data[t] = ambil_tabel(base_id, t, token)
            except SystemExit as e:
                if "NOT_FOUND" in str(e) or "404" in str(e):
                    print(f"  ! Tabel '{t}' tidak ditemukan di Airtable — dilewati.")
                    data[t] = []
                else:
                    raise
            print(f"  · {t}: {len(data[t])} baris")
        return data, "airtable"
    path = os.environ.get("CONTOH_DATA") or os.path.join(root, "data", "contoh.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for t in TABEL:
        data.setdefault(t, [])
    return data, "contoh"
