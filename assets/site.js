/* Fajar Sikka — skrip kecil: menu, saring program, salin tautan, lightbox foto */
(function () {
  "use strict";
  var d = document;

  // Menu ponsel
  var tombol = d.querySelector(".tombol-menu"), nav = d.getElementById("nav-utama");
  if (tombol && nav) {
    tombol.addEventListener("click", function () {
      var buka = tombol.getAttribute("aria-expanded") !== "true";
      tombol.setAttribute("aria-expanded", String(buka));
      nav.classList.toggle("buka", buka);
    });
    d.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && nav.classList.contains("buka")) { tombol.click(); tombol.focus(); }
    });
  }

  // Saring program berdasarkan bidang
  var saring = d.querySelector(".saring[hidden]"), daftar = d.querySelector("[data-daftar-saring]");
  if (saring && daftar) {
    saring.hidden = false;
    saring.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-saring]");
      if (!b) return;
      var nilai = b.getAttribute("data-saring");
      saring.querySelectorAll("[data-saring]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      daftar.querySelectorAll("[data-bidang]").forEach(function (k) {
        k.hidden = !!nilai && k.getAttribute("data-bidang") !== nilai;
      });
    });
  }

  // Tombol salin (nomor rekening / tautan)
  d.querySelectorAll("[data-salin]").forEach(function (b) {
    b.addEventListener("click", function () {
      var teks = b.getAttribute("data-salin"), asli = b.textContent;
      var selesai = function () { b.textContent = b.getAttribute("data-tersalin") || "✓"; setTimeout(function () { b.textContent = asli; }, 2000); };
      if (navigator.clipboard) navigator.clipboard.writeText(teks).then(selesai, function () {});
      else { var t = d.createElement("textarea"); t.value = teks; d.body.appendChild(t); t.select(); try { d.execCommand("copy"); selesai(); } catch (e) {} t.remove(); }
    });
  });

  // Lightbox foto
  var tautan = Array.prototype.slice.call(d.querySelectorAll("[data-lightbox]"));
  if (!tautan.length || typeof HTMLDialogElement !== "function") return;
  var en = d.documentElement.lang === "en";
  var dlg = d.createElement("dialog");
  dlg.className = "lightbox";
  dlg.setAttribute("aria-label", en ? "Photo viewer" : "Penampil foto");
  dlg.innerHTML = '<div class="lightbox-isi"><img alt=""></div>' +
    '<button class="lb-tutup" type="button" aria-label="' + (en ? "Close" : "Tutup") + '">✕</button>' +
    '<button class="lb-kiri" type="button" aria-label="' + (en ? "Previous photo" : "Foto sebelumnya") + '">‹</button>' +
    '<button class="lb-kanan" type="button" aria-label="' + (en ? "Next photo" : "Foto berikutnya") + '">›</button>' +
    '<p class="lb-hitung" aria-live="polite"></p>';
  d.body.appendChild(dlg);
  var img = dlg.querySelector("img"), hitung = dlg.querySelector(".lb-hitung"), i = 0;
  function tampil(n) {
    i = (n + tautan.length) % tautan.length;
    var a = tautan[i], asal = a.querySelector("img");
    img.removeAttribute("srcset");
    img.src = a.getAttribute("href");
    if (a.dataset.srcset) { img.srcset = a.dataset.srcset; img.sizes = "100vw"; }
    img.alt = asal ? asal.alt : "";
    hitung.textContent = (i + 1) + " / " + tautan.length;
    var satu = tautan.length < 2;
    dlg.querySelector(".lb-kiri").hidden = satu; dlg.querySelector(".lb-kanan").hidden = satu;
  }
  tautan.forEach(function (a, n) {
    a.addEventListener("click", function (ev) { ev.preventDefault(); tampil(n); dlg.showModal(); });
  });
  dlg.querySelector(".lb-tutup").addEventListener("click", function () { dlg.close(); });
  dlg.querySelector(".lb-kiri").addEventListener("click", function () { tampil(i - 1); });
  dlg.querySelector(".lb-kanan").addEventListener("click", function () { tampil(i + 1); });
  dlg.addEventListener("click", function (ev) { if (ev.target === dlg || ev.target.classList.contains("lightbox-isi")) dlg.close(); });
  dlg.addEventListener("keydown", function (ev) {
    if (ev.key === "ArrowLeft") tampil(i - 1);
    if (ev.key === "ArrowRight") tampil(i + 1);
  });
  var x0 = null;
  dlg.addEventListener("touchstart", function (ev) { x0 = ev.touches[0].clientX; }, { passive: true });
  dlg.addEventListener("touchend", function (ev) {
    if (x0 === null) return;
    var dx = ev.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 50) tampil(i + (dx < 0 ? 1 : -1));
  });
})();
