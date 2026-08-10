(function () {
  const STORAGE_KEY = "theme";
  const ICON_SUN =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const ICON_MOON =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

  function getStoredTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : null;
  }

  function effectiveTheme() {
    return getStoredTheme() || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }

  function updateToggleIcon() {
    const el = document.getElementById("theme-toggle-icon");
    if (!el) return;
    el.innerHTML = effectiveTheme() === "dark" ? ICON_SUN : ICON_MOON;
  }

  function applyTheme(theme) {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
    else document.documentElement.removeAttribute("data-theme");
    updateToggleIcon();
  }

  applyTheme(getStoredTheme());

  window.toggleTheme = function () {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
    document.dispatchEvent(new CustomEvent("themechange", { detail: { theme: next } }));
  };

  document.addEventListener("DOMContentLoaded", updateToggleIcon);
})();
