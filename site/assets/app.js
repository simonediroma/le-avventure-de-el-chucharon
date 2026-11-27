(() => {
  const cfg = window.CHUCHARON_CONFIG || {};
  const $ = (s) => document.querySelector(s);
  let catalog = null;

  document.getElementById("gh-link").href = `https://github.com/${cfg.repo}`;
  if (cfg.printUrl) { $("#buy-print").href = cfg.printUrl; $(".menu-buy").href = cfg.printUrl; }

  // ---------- Menu mobile ----------
  const toggle = $(".menu-toggle"), menu = $("#menu");
  const setMenu = (open) => {
    menu.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Chiudi il menu" : "Apri il menu");
  };
  toggle.addEventListener("click", () => setMenu(!menu.classList.contains("open")));
  menu.addEventListener("click", (e) => { if (e.target.closest("a")) setMenu(false); });
  document.addEventListener("click", (e) => { if (!e.target.closest(".nav")) setMenu(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });

  // ---------- Galleria ----------
  async function load() {
    const res = await fetch("data/chapters.json", { cache: "no-cache" });
    catalog = await res.json();
    if (catalog.cover) $("#hero-cover").src = catalog.cover;
    renderGallery();
    renderBuilder();
  }

  function renderGallery() {
    const el = $("#gallery");
    el.innerHTML = "";
    for (const ch of catalog.chapters.filter((c) => c.ready)) {
      const cover = ch.cover || ch.pages[0]?.image;
      const isCommunity = ch.issue != null;
      const card = document.createElement("article");
      card.className = "card";
      card.innerHTML = `
        <img loading="lazy" src="${cover}" alt="${esc(ch.title)}">
        <div class="body">
          <span class="tag ${isCommunity ? "community" : ""}">${ch.kind === "core" ? "Storia di Elena" : isCommunity ? "Dalla community" : "Capitolo"}</span>
          <h3>${esc(ch.title)}</h3>
          ${ch.pain_point ? `<span class="muted small">${esc(ch.pain_point)}</span>` : ""}
          ${ch.author ? `<span class="author">Autore: <strong>${esc(ch.author)}</strong></span>` : ""}
          <div class="actions">
            <button type="button" data-read>Leggi</button>
            ${ch.pdf ? `<a href="${ch.pdf}" download>PDF</a>` : ""}
          </div>
        </div>`;
      card.querySelector("img").onclick = card.querySelector("[data-read]").onclick = () => openReader(ch);
      el.appendChild(card);
    }
  }

  // ---------- Lettore ----------
  const reader = $("#reader"), rImg = $("#r-img"), rText = $("#r-text");
  let rPages = [], rIdx = 0, rTitle = "";

  function openReader(ch) {
    rPages = ch.pages.filter((p) => p.image);
    rIdx = 0; rTitle = ch.title;
    $("#r-title").textContent = ch.title;
    $("#r-dots").innerHTML = rPages.map(() => "<i></i>").join("");
    showPage();
    reader.showModal();
    document.body.style.overflow = "hidden";
  }
  function showPage() {
    const p = rPages[rIdx];
    rImg.classList.add("loading");
    rImg.onload = () => rImg.classList.remove("loading");
    rImg.src = p.image;
    rImg.alt = `${rTitle} — pagina ${rIdx + 1}`;
    renderText(p);
    $("#r-count").textContent = `Pagina ${rIdx + 1} di ${rPages.length}`;
    $("#r-prev").disabled = rIdx === 0;
    const last = rIdx === rPages.length - 1;
    $("#r-next").innerHTML = last ? "<span>Fine</span> ✓" : "<span>Avanti</span> ›";
    $("#r-next").setAttribute("aria-label", last ? "Chiudi il lettore" : "Pagina successiva");
    $("#r-dots").querySelectorAll("i").forEach((d, i) => d.classList.toggle("on", i === rIdx));
    $("#r-stage").scrollTop = 0;
    $(".r-text-wrap").scrollTop = 0;
    if (rPages[rIdx + 1]) new Image().src = rPages[rIdx + 1].image; // precarica la successiva
  }
  // Testo: le strofe tra 🎵 diventano un blocco "canzone", il resto resta narrazione
  function renderText(p) {
    // 2ª edizione: ogni pagina è un'immagine completa (testo già impaginato sulla cornice)
    $("#r-stage").classList.toggle("is-cover", p.kind === "cover" || !p.text);
    if (!p.text) { rText.replaceChildren(); return; }
    rText.className = "r-text";
    rText.replaceChildren();
    let inSong = false, songEl = null;
    for (const line of p.text.split("\n")) {
      const marks = (line.match(/🎵/g) || []).length;
      if (inSong || marks) {
        if (!songEl) { songEl = document.createElement("span"); songEl.className = "r-song"; rText.append(songEl); }
        songEl.append(line.replace(/🎵/g, "").trim().replace(/\s*\/\s*/g, "\n") + "\n");
        if (marks % 2) inSong = !inSong;
        if (!inSong) songEl = null;
      } else {
        rText.append(line + "\n");
      }
    }
  }
  const go = (d) => { const n = rIdx + d; if (n >= 0 && n < rPages.length) { rIdx = n; showPage(); } };
  $("#r-prev").onclick = () => go(-1);
  $("#r-next").onclick = () => (rIdx === rPages.length - 1 ? reader.close() : go(1));
  $(".r-close").onclick = () => reader.close();
  reader.addEventListener("close", () => { document.body.style.overflow = ""; });
  reader.addEventListener("click", (e) => { if (e.target === reader) reader.close(); }); // click sullo sfondo
  document.addEventListener("keydown", (e) => {
    if (!reader.open) return;
    if (e.key === "ArrowRight") go(1);
    if (e.key === "ArrowLeft") go(-1);
  });
  // Swipe su mobile
  let tx = null, ty = null;
  $("#r-stage").addEventListener("touchstart", (e) => { tx = e.touches[0].clientX; ty = e.touches[0].clientY; }, { passive: true });
  $("#r-stage").addEventListener("touchend", (e) => {
    if (tx === null) return;
    const dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) go(dx < 0 ? 1 : -1);
    tx = ty = null;
  }, { passive: true });

  // ---------- Crea il tuo libro ----------
  function renderBuilder() {
    const list = $("#builder-list");
    list.innerHTML = "";
    const core = catalog.chapters.filter((c) => c.kind === "core");
    const lockedRow = (ch) => `<label class="locked"><input type="checkbox" checked disabled> ${esc(ch.title)}</label>`;
    if (core[0]) list.insertAdjacentHTML("beforeend", lockedRow(core[0]));
    for (const ch of catalog.chapters) {
      if (ch.kind === "core" || !ch.pdf) continue;
      list.insertAdjacentHTML("beforeend",
        `<label class="sortable"><span class="handle" aria-hidden="true" title="Trascina per riordinare">⠿</span>` +
        `<input type="checkbox" name="ch" value="${ch.slug}" checked> <span class="t">${esc(ch.title)}</span>` +
        `<span class="mv"><button type="button" data-mv="-1" aria-label="Sposta su">▲</button>` +
        `<button type="button" data-mv="1" aria-label="Sposta giù">▼</button></span></label>`);
    }
    for (const ch of core.slice(1)) list.insertAdjacentHTML("beforeend", lockedRow(ch));
  }

  // Riordino capitoli: drag & drop (mouse e touch via Pointer Events) + pulsanti ▲▼
  (() => {
    const list = $("#builder-list");
    let drag = null;
    list.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-mv]");
      if (!b) return;
      e.preventDefault();
      const row = b.closest(".sortable");
      const sib = +b.dataset.mv < 0 ? row.previousElementSibling : row.nextElementSibling;
      if (!sib || !sib.classList.contains("sortable")) return;
      +b.dataset.mv < 0 ? sib.before(row) : sib.after(row);
      b.focus();
    });
    list.addEventListener("pointerdown", (e) => {
      const h = e.target.closest(".handle");
      if (!h) return;
      e.preventDefault();
      drag = h.closest(".sortable");
      drag.classList.add("dragging");
      h.setPointerCapture(e.pointerId);
    });
    list.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const rows = [...list.querySelectorAll(".sortable:not(.dragging)")];
      const over = rows.find((r) => {
        const b = r.getBoundingClientRect();
        return e.clientY >= b.top && e.clientY <= b.bottom && e.clientX >= b.left && e.clientX <= b.right;
      });
      if (!over) return;
      const b = over.getBoundingClientRect();
      const after = b.width > b.height * 3 && list.offsetWidth < b.width * 1.5
        ? e.clientY > b.top + b.height / 2      // lista a una colonna
        : e.clientX > b.left + b.width / 2;     // griglia
      after ? over.after(drag) : over.before(drag);
    });
    const end = () => { if (drag) { drag.classList.remove("dragging"); drag = null; } };
    list.addEventListener("pointerup", end);
    list.addEventListener("pointercancel", end);
  })();

  $("#builder").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#b-go"), status = $("#b-status");
    const chosen = [...document.querySelectorAll('input[name="ch"]:checked')].map((i) => i.value);
    btn.disabled = true; status.textContent = "Sto componendo il tuo libro…";
    try {
      const { PDFDocument } = PDFLib;
      const out = await PDFDocument.create();
      const parts = [catalog.pdf.inizio, ...chosen.map((s) => catalog.chapters.find((c) => c.slug === s).pdf), catalog.pdf.fine];
      for (const [i, url] of parts.entries()) {
        const src = await PDFDocument.load(await (await fetch(url)).arrayBuffer());
        let idx = src.getPageIndices();
        if (i === 0 && !$("#b-cover").checked) idx = idx.slice(1); // la prima pagina di inizio.pdf è la copertina
        (await out.copyPages(src, idx)).forEach((p) => out.addPage(p));
      }
      out.setTitle("Le Avventure de El Chucharon — la mia edizione");
      const blob = new Blob([await out.save()], { type: "application/pdf" });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "el-chucharon-la-mia-edizione.pdf" });
      a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 10000);
      status.textContent = `Fatto! ${out.getPageCount()} pagine.`;
    } catch (err) {
      console.error(err); status.textContent = "Ops, qualcosa è andato storto. Riprova.";
    } finally { btn.disabled = false; }
  });

  // ---------- Proposta ----------
  const TITLES = {
    nome_bambino: "Nome del bambino o della bambina", eta: "Età", aspetto: "Com'è fatto/a (aspetto e vestiti)",
    pain_point: "Il problema da risolvere (pain point)", gancio_messico: "Il gancio con il Messico",
    genitori: "Chi accompagna il bambino", comicita_genitori: "La scena comica dei genitori",
    ambientazione: "Dove si svolge la scena", soluzione: "Come lo aiuta El Chucharito (facoltativo)",
    autore: "Firma dell'autore della proposta",
  };

  if (cfg.proposalEndpoint && cfg.turnstileSiteKey) {
    const s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js"; s.async = true;
    document.head.appendChild(s);
    $("#turnstile").innerHTML = `<div class="cf-turnstile" data-sitekey="${cfg.turnstileSiteKey}"></div>`;
  }

  $("#proposal").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target), status = $("#p-status");
    const data = Object.fromEntries(Object.keys(TITLES).map((k) => [k, (fd.get(k) || "").toString().trim()]));
    status.className = "full";

    if (!cfg.proposalEndpoint) {
      // Fallback: Issue Form di GitHub precompilato (richiede un account GitHub)
      const q = new URLSearchParams({ template: "proposta-capitolo.yml", title: `Proposta: ${data.nome_bambino}`, ...data });
      window.open(`https://github.com/${cfg.repo}/issues/new?${q}`, "_blank", "noopener");
      status.textContent = "Ti abbiamo aperto il modulo su GitHub: conferma l'invio da lì.";
      return;
    }
    status.textContent = "Invio in corso…";
    try {
      const res = await fetch(cfg.proposalEndpoint, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, turnstile: fd.get("cf-turnstile-response") || "" }),
      });
      const out = await res.json();
      if (!res.ok) throw new Error(out.error || res.statusText);
      status.className = "full ok";
      status.innerHTML = `Grazie! Proposta ricevuta. Segui la validazione qui: <a href="${out.url}" target="_blank" rel="noopener">${out.url}</a>`;
      e.target.reset();
    } catch (err) {
      status.className = "full err"; status.textContent = `Invio non riuscito: ${err.message}`;
    }
  });

  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  load().catch((e) => { console.error(e); $("#gallery").textContent = "Catalogo non disponibile."; });
})();
