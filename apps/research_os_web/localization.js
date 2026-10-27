(() => {
  "use strict";
  const SELECTOR = "#mainLocaleSelect";
  const STORAGE_KEY = "research-os-locale";
  const fallback = "th";
  const state = { locale: fallback, catalog: {} };
  const $ = (selector) => document.querySelector(selector);
  const t = (key, defaultValue = key) => state.catalog[key] ?? defaultValue;

  async function loadCatalog(locale) {
    const response = await fetch(`/tools/localization_center/locales/${locale}.json`, { credentials: "same-origin" });
    if (!response.ok) throw new Error(`Catalog request failed (HTTP ${response.status})`);
    const catalog = await response.json();
    if (!catalog || Array.isArray(catalog) || typeof catalog !== "object") throw new Error("Catalog has an invalid shape");
    return catalog;
  }

  function applyCatalog() {
    document.documentElement.lang = state.locale;
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      const key = node.dataset.i18n;
      if (Object.prototype.hasOwnProperty.call(state.catalog, key)) node.textContent = state.catalog[key];
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      const key = node.dataset.i18nPlaceholder;
      if (Object.prototype.hasOwnProperty.call(state.catalog, key)) node.setAttribute("placeholder", state.catalog[key]);
    });
    const select = $(SELECTOR);
    if (select) select.value = state.locale;
    document.title = state.locale === "th" ? "Research OS 3.2 — ค้นคว้าเชิงลึก" : "Research OS 3.2 — Wide Research";
    document.dispatchEvent(new CustomEvent("researchos:localechange", { detail: { locale: state.locale } }));
  }

  async function setLocale(locale) {
    const safeLocale = locale === "en" ? "en" : "th";
    try {
      state.catalog = await loadCatalog(safeLocale);
      state.locale = safeLocale;
      try { localStorage.setItem(STORAGE_KEY, safeLocale); } catch (_) {}
      applyCatalog();
    } catch (error) {
      console.error("Localization catalog could not be loaded:", error);
      if (safeLocale !== fallback) {
        try {
          state.catalog = await loadCatalog(fallback);
          state.locale = fallback;
          applyCatalog();
        } catch (_) {
          const select = $(SELECTOR);
          if (select) select.setAttribute("aria-invalid", "true");
        }
      }
    }
  }

  window.ResearchOSLocalization = {
    t,
    get locale() { return state.locale; },
    setLocale
  };

  document.addEventListener("DOMContentLoaded", () => {
    const select = $(SELECTOR);
    let initial = fallback;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "th") initial = saved;
    } catch (_) {}
    if (select) select.addEventListener("change", () => setLocale(select.value));
    setLocale(initial);
  });
})();