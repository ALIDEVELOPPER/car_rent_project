// Runtime i18n. Les dictionnaires sont chargés en amont (i18n/fr.js, i18n/ar.js)
// dans window.I18N, donc t() est disponible de façon synchrone avant Alpine.
// Le changement de langue recharge la page (simple et fiable).
(function () {
  var DIRS = { fr: "ltr", ar: "rtl" };
  var KEY = "lang";

  function current() {
    var l = localStorage.getItem(KEY);
    return DIRS[l] ? l : "fr";
  }

  var lang = current();
  document.documentElement.lang = lang;
  document.documentElement.dir = DIRS[lang];

  var I18N = window.I18N || {};
  var fallback = I18N.fr || {};
  var dict = I18N[lang] || fallback;

  function lookup(d, key) {
    var parts = key.split(".");
    var o = d;
    for (var i = 0; i < parts.length; i++) {
      if (o == null) return null;
      o = o[parts[i]];
    }
    return o;
  }

  window.t = function (key, params) {
    var s = lookup(dict, key);
    if (s == null) s = lookup(fallback, key);
    if (s == null) return key;
    if (params) {
      s = String(s).replace(/\{(\w+)\}/g, function (_, k) {
        return params[k] != null ? params[k] : "{" + k + "}";
      });
    }
    return s;
  };

  // Traduit un message d'erreur renvoyé par le serveur (correspondance exacte,
  // sinon on renvoie le message tel quel).
  window.tErr = function (msg) {
    if (!msg) return msg;
    var e = (dict.errors && dict.errors[msg]) || (fallback.errors && fallback.errors[msg]);
    return e || msg;
  };

  window.currentLang = current;

  window.setLang = function (code) {
    if (!DIRS[code] || code === current()) return;
    localStorage.setItem(KEY, code);
    fetch("/api/parametres/agence", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ langue: code }),
    })
      .catch(function () {})
      .then(function () {
        window.location.reload();
      });
  };

  // Mémorise une langue sans recharger (utilisé juste avant une redirection,
  // ex. après login pour restaurer le choix du gérant enregistré côté serveur).
  window.rememberLang = function (code) {
    if (DIRS[code]) localStorage.setItem(KEY, code);
  };

  function apply(root) {
    root = root || document;
    root.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = window.t(el.getAttribute("data-i18n"));
    });
    root.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      el.setAttribute("placeholder", window.t(el.getAttribute("data-i18n-ph")));
    });
    root.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      el.setAttribute("aria-label", window.t(el.getAttribute("data-i18n-aria")));
    });
    root.querySelectorAll("[data-i18n-title-key]").forEach(function (el) {
      document.title = window.t(el.getAttribute("data-i18n-title-key"));
    });
  }

  window.applyI18n = apply;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      apply(document);
    });
  } else {
    apply(document);
  }

  // Bouton de bascule rapide FR / ع (élément avec id="lang-toggle").
  window.toggleLang = function () {
    window.setLang(current() === "ar" ? "fr" : "ar");
  };
})();
