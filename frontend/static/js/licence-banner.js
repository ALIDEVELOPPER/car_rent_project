// Contrôle de licence côté client, chargé sur toutes les pages authentifiées.
//
//  - affiche un bandeau non bloquant pendant l'essai (et la période de grâce) ;
//  - réinterroge le serveur périodiquement même si l'utilisateur ne navigue pas,
//    et redirige vers /activation dès que l'accès est bloqué (suspendu, essai
//    terminé...). Ça évite qu'un client qui laisse la fenêtre ouverte continue
//    d'utiliser l'app indéfiniment sans payer.
(function () {
  var POLL_MS = 5 * 60 * 1000; // 5 min

  function frenchDate(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("fr-FR", {
        day: "numeric",
        month: "long",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return "";
    }
  }

  function removeBanner() {
    var existing = document.getElementById("licence-banner");
    if (existing) existing.remove();
  }

  function renderBanner(state) {
    removeBanner();
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
    bar.id = "licence-banner";
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

  function apply(state) {
    if (state && state.blocked) {
      // Accès révoqué pendant la session : on sort immédiatement.
      window.location.href = "/activation";
      return;
    }
    renderBanner(state);
  }

  function check(force) {
    fetch("/api/licence/status" + (force ? "?force=1" : ""))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(apply)
      .catch(function () {});
  }

  function start() {
    check(false);
    setInterval(function () { check(true); }, POLL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
