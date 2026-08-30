// Bandeau non bloquant affiché pendant l'essai gratuit (et pendant la période
// de grâce une fois l'essai terminé). Le blocage réel est géré côté serveur par
// le gate Flask (redirection vers /activation).
(function () {
  function frenchDate(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
    } catch (e) {
      return "";
    }
  }

  function render(state) {
    if (!state || state.blocked) return;
    if (state.reason !== "essai" && state.reason !== "essai_grace") return;

    var urgent = state.reason === "essai_grace";
    var days = state.jours_essai_restants;

    var text;
    if (urgent) {
      text =
        "Votre essai gratuit est terminé. L'accès sera bloqué le " +
        frenchDate(state.bloque_le) +
        ". Contactez-nous pour activer : ";
    } else if (typeof days === "number") {
      text =
        "Version d'essai gratuite — " +
        days +
        (days > 1 ? " jours restants" : " jour restant") +
        ". ";
    } else {
      text = "Version d'essai gratuite. ";
    }

    var bar = document.createElement("div");
    bar.setAttribute("role", "status");
    bar.style.cssText =
      "position:sticky;top:0;z-index:9999;padding:8px 16px;text-align:center;" +
      "font-size:13px;font-weight:600;line-height:1.4;" +
      (urgent
        ? "background:#dc2626;color:#fff;"
        : "background:#fef3c7;color:#92400e;border-bottom:1px solid #fcd34d;");

    var contact = [state.contact_email, state.contact_phone].filter(Boolean).join("  ·  ");
    bar.textContent = text;
    if (urgent && contact) {
      var strong = document.createElement("span");
      strong.textContent = contact;
      bar.appendChild(strong);
    }

    document.body.insertBefore(bar, document.body.firstChild);
  }

  function check() {
    fetch("/api/licence/status")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(render)
      .catch(function () {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", check);
  } else {
    check();
  }
})();
