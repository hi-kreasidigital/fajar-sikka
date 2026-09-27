"""Pengubah Markdown sederhana untuk teks rich text dari Airtable.

Mendukung: judul (#, ##, ###), paragraf, huruf tebal/miring/coret, kode,
tautan, daftar berpoin & bernomor, kutipan, garis pemisah, dan penanda
foto [foto:1] untuk menyisipkan foto dari kolom lampiran.
"""
import html
import re

_ESC = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>~|])")


def _inline(text: str) -> str:
    # 1) simpan karakter yang di-escape Airtable (mis. \- atau \.)
    stash = []

    def keep(m):
        stash.append(html.escape(m.group(1)))
        return f"\x00{len(stash) - 1}\x00"

    text = _ESC.sub(keep, text)
    text = html.escape(text, quote=False)

    # kode inline
    codes = []

    def code(m):
        codes.append(f"<code>{m.group(1)}</code>")
        return f"\x01{len(codes) - 1}\x01"

    text = re.sub(r"`([^`]+)`", code, text)

    # tautan [teks](url)
    def link(m):
        label, url = m.group(1), m.group(2).strip()
        if not re.match(r"^(https?://|mailto:|tel:|/|#)", url):
            url = "https://" + url
        ext = url.startswith("http")
        attrs = ' rel="noopener" target="_blank"' if ext else ""
        return f'<a href="{html.escape(url, quote=True)}"{attrs}>{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    # tebal, miring, coret
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)

    text = re.sub(r"\x01(\d+)\x01", lambda m: codes[int(m.group(1))], text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
    return text


FOTO_RE = re.compile(r"^\s*\[foto\s*:\s*(\d+)\s*\]\s*$", re.I)


def render(md: str, foto=None) -> str:
    """Ubah Markdown menjadi HTML.

    foto: fungsi opsional f(nomor) -> html untuk penanda [foto:n].
    """
    if not md:
        return ""
    lines = md.replace("\r\n", "\n").split("\n")
    out = []
    para = []
    lst = None  # ("ul"|"ol", [items])
    quote = []
    code = None

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + "<br>".join(_inline(x) for x in para) + "</p>")
            para = []

    def flush_list():
        nonlocal lst
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{tag}>")
            lst = None

    def flush_quote():
        nonlocal quote
        if quote:
            out.append("<blockquote>" + render("\n".join(quote), foto) + "</blockquote>")
            quote = []

    def flush_all():
        flush_para()
        flush_list()
        flush_quote()

    for raw in lines:
        line = raw.rstrip()
        if code is not None:
            if line.strip().startswith("```"):
                out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
                code = None
            else:
                code.append(raw)
            continue
        if line.strip().startswith("```"):
            flush_all()
            code = []
            continue
        if not line.strip():
            flush_all()
            continue
        if line.lstrip().startswith(">"):
            flush_para()
            flush_list()
            quote.append(re.sub(r"^\s*>\s?", "", line))
            continue
        else:
            flush_quote()
        m = FOTO_RE.match(line)
        if m:
            flush_all()
            if foto:
                out.append(foto(int(m.group(1))))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_all()
            lvl = min(len(m.group(1)) + 1, 4)  # # -> h2 (h1 dipakai judul halaman)
            out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>")
            continue
        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", line):
            flush_all()
            out.append("<hr>")
            continue
        m = re.match(r"^\s*[-*+]\s+(\[[ xX]\]\s+)?(.*)$", line)
        if m:
            flush_para()
            if not lst or lst[0] != "ul":
                flush_list()
                lst = ("ul", [])
            lst[1].append(_inline(m.group(2)))
            continue
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if m:
            flush_para()
            if not lst or lst[0] != "ol":
                flush_list()
                lst = ("ol", [])
            lst[1].append(_inline(m.group(1)))
            continue
        if lst and raw.startswith(("  ", "\t")):
            lst[1][-1] += " " + _inline(line.strip())
            continue
        flush_list()
        para.append(line.strip())
    if code is not None:
        out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
    flush_all()
    return "\n".join(out)


def plain(md: str) -> str:
    """Teks polos (untuk meta description)."""
    if not md:
        return ""
    t = FOTO_RE.sub("", md)
    t = re.sub(r"\[foto\s*:\s*\d+\s*\]", "", t, flags=re.I)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[#>*_`~]|\\", "", t)
    t = re.sub(r"^\s*[-+]\s+", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()


def excerpt(md: str, n: int = 155) -> str:
    t = plain(md)
    if len(t) <= n:
        return t
    cut = t[: n - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:—-") + "…"
