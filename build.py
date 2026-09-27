#!/usr/bin/env python3
"""Bangun website Fajar Sikka ke folder dist/.

Pemakaian:
    python build.py                 # pakai Airtable bila AIRTABLE_TOKEN ada, jika tidak pakai data/contoh.json
    python build.py --lihat         # bangun lalu buka pratinjau di http://localhost:8000
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from generator.situs import Situs  # noqa: E402

if __name__ == "__main__":
    s = Situs(ROOT)
    s.bangun()
    if "--lihat" in sys.argv:
        import functools
        import http.server
        port = 8000
        if s.base:
            print(f"Catatan: alamat memakai sub-folder '{s.base}'. Untuk pratinjau lokal jalankan tanpa "
                  "SITE_URL/PAGES_BASE_URL agar alamatnya http://localhost:8000.")
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=s.dist)
        print(f"Pratinjau: http://localhost:{port}  (Ctrl+C untuk berhenti)")
        http.server.ThreadingHTTPServer(("", port), h).serve_forever()
