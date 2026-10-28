(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { source: {}, catalogs: { en: {}, th: {} }, locale: "th", importName: "" };
  const placeholders = (value) => [...String(value).matchAll(/\{([A-Za-z_][A-Za-z0-9_.-]*)\}/g)].map((m) => m[1]).sort();
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  function validateCatalog(source, target) {
    const errors = [];
    for (const key of Object.keys(source)) {
      if (!(key in target)) { errors.push(`Missing key: ${key}`); continue; }
      if (typeof target[key] !== "string") { errors.push(`Translation is not a string: ${key}`); continue; }
      if (!target[key].trim()) errors.push(`Empty translation: ${key}`);
      if (!same(placeholders(source[key]), placeholders(target[key]))) errors.push(`Placeholder mismatch: ${key}`);
    }
    for (const key of Object.keys(target)) if (!(key in source)) errors.push(`Unknown key: ${key}`);
    return errors;
  }
  function showNotice(title, message) {
    $("noticeTitle").textContent = title;
    $("noticeText").textContent = message;
    const dialog = $("noticeDialog");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else window.alert(title + "\n\n" + message);
  }
  function setGate(errors) {
    const gate = $("gate");
    gate.classList.toggle("pass", errors.length === 0);
    gate.classList.toggle("fail", errors.length > 0);
    $("gateTitle").textContent = errors.length ? `FAIL · ${errors.length} issue(s) found` : "PASS · Catalog checks passed";
    $("gateMessage").textContent = errors.length ? errors.slice(0, 4).join(" · ") + (errors.length > 4 ? ` · +${errors.length - 4} more` : "") : "Keys, string values, and placeholders match the source catalog.";
    $("gate").setAttribute("aria-label", $("gateTitle").textContent + ". " + $("gateMessage").textContent);
  }
  function render() {
    const locale = state.locale;
    const target = state.catalogs[locale];
    const errors = validateCatalog(state.source, target);
    const keys = Object.keys(state.source).sort();
    const rows = $("translationRows");
    rows.replaceChildren();
    for (const key of keys) {
      const tr = document.createElement("tr");
      tr.classList.toggle("missing", typeof target[key] !== "string" || !target[key].trim());
      const keyCell = document.createElement("td"); keyCell.className = "key"; keyCell.textContent = key;
      const sourceCell = document.createElement("td"); sourceCell.className = "source"; sourceCell.textContent = state.source[key];
      const targetCell = document.createElement("td"); targetCell.className = "target";
      const textarea = document.createElement("textarea"); textarea.value = typeof target[key] === "string" ? target[key] : ""; textarea.setAttribute("aria-label", `${key} translation`); textarea.dataset.key = key;
      textarea.addEventListener("input", () => { target[key] = textarea.value; tr.classList.toggle("missing", !textarea.value.trim()); updateStats(); setGate(validateCatalog(state.source, target)); });
      targetCell.append(textarea); tr.append(keyCell, sourceCell, targetCell); rows.append(tr);
    }
    $("targetHeading").textContent = locale === "th" ? "Thai translation" : "English translation";
    $("totalCount").textContent = keys.length;
    updateStats();
    setGate(errors);
    filterRows();
  }
  function updateStats() {
    const target = state.catalogs[state.locale], keys = Object.keys(state.source);
    const translated = keys.filter((key) => typeof target[key] === "string" && target[key].trim()).length;
    $("translatedCount").textContent = translated;
    $("missingCount").textContent = keys.length - translated;
    $("completionCount").textContent = keys.length ? Math.round(translated / keys.length * 100) + "%" : "0%";
  }
  function filterRows() {
    const query = $("searchInput").value.trim().toLowerCase();
    for (const row of $("translationRows").rows) row.hidden = !!query && !row.textContent.toLowerCase().includes(query);
  }
  function downloadJson() {
    const errors = validateCatalog(state.source, state.catalogs[state.locale]);
    if (errors.length) { showNotice("Export blocked", "Resolve Quality Gate issues before exporting. " + errors.slice(0, 6).join("; ")); return; }
    const blob = new Blob([JSON.stringify(state.catalogs[state.locale], null, 2) + "\n"], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${state.locale}.json`; document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
  }
  async function importJson(file) {
    try {
      const parsed = JSON.parse(await file.text());
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object" || Object.values(parsed).some((value) => typeof value !== "string")) throw new Error("Expected a JSON object containing only string values.");
      state.catalogs[state.locale] = parsed;
      render();
      const errors = validateCatalog(state.source, parsed);
      showNotice(errors.length ? "Imported with issues" : "Import complete", errors.length ? `Loaded ${file.name}, but Quality Gate found ${errors.length} issue(s). Review the highlighted report before exporting.` : `Loaded ${file.name}. Catalog checks passed.`);
    } catch (error) { showNotice("Import failed", `Could not load JSON: ${error.message}`); }
    finally { $("importInput").value = ""; }
  }
  async function init() {
    try {
      const [source, thai, english] = await Promise.all([
        fetch("./locales/en.json").then((r) => { if (!r.ok) throw new Error("Could not load source catalog"); return r.json(); }),
        fetch("./locales/th.json").then((r) => { if (!r.ok) throw new Error("Could not load Thai catalog"); return r.json(); }),
        fetch("./locales/en.json").then((r) => { if (!r.ok) throw new Error("Could not load English catalog"); return r.json(); })
      ]);
      if ([source, thai, english].some((catalog) => !catalog || Array.isArray(catalog) || typeof catalog !== "object" || Object.values(catalog).some((value) => typeof value !== "string"))) throw new Error("Catalog schema must be a JSON object of string values.");
      state.source = source; state.catalogs.th = thai; state.catalogs.en = { ...english };
      render();
    } catch (error) {
      $("translationRows").innerHTML = ""; const row = document.createElement("tr"); const cell = document.createElement("td"); cell.colSpan = 3; cell.textContent = `Unable to load catalogs: ${error.message}. Serve this folder over localhost rather than opening file:// directly.`; row.append(cell); $("translationRows").append(row);
      setGate(["Catalogs failed to load."]);
    }
  }
  $("localeSelect").addEventListener("change", (event) => { state.locale = event.target.value; render(); });
  $("searchInput").addEventListener("input", filterRows);
  $("exportButton").addEventListener("click", downloadJson);
  $("importButton").addEventListener("click", () => $("importInput").click());
  $("importInput").addEventListener("change", (event) => { const file = event.target.files && event.target.files[0]; if (file) importJson(file); });
  $("closeNotice").addEventListener("click", () => $("noticeDialog").close());
  init();
})();