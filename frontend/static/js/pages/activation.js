const BLOCKED_MESSAGES = {
  connexion_requise:
    "Une connexion internet est requise au premier lancement pour activer votre essai gratuit. Connectez-vous à internet puis réessayez.",
  essai_expire:
    "Votre période d'essai gratuit de 7 jours est terminée. Contactez-nous pour activer votre abonnement.",
  suspendu:
    "Votre accès a été suspendu. Contactez-nous pour régulariser votre situation.",
  verification_impossible:
    "Impossible de vérifier votre abonnement depuis plusieurs jours. Connectez-vous à internet puis réessayez.",
  reverification_requise:
    "Votre abonnement doit être revérifié. Connectez-vous à internet puis réessayez.",
};

function activationPage() {
  return {
    checking: true,
    blockedMessage: "",
    contact: "",
    error: "",
    loading: false,

    async init() {
      await this.refreshState();
    },

    async refreshState(force) {
      this.checking = true;
      try {
        const state = await Api.get(force ? "/licence/status?force=1" : "/licence/status");
        if (!state.blocked) {
          window.location.href = "/";
          return;
        }
        this.blockedMessage =
          BLOCKED_MESSAGES[state.reason] ||
          "Votre accès est actuellement bloqué. Contactez-nous pour plus d'informations.";
        const parts = [];
        if (state.contact_email) parts.push(state.contact_email);
        if (state.contact_phone) parts.push(state.contact_phone);
        this.contact = parts.join("  ·  ");
      } catch (err) {
        this.blockedMessage =
          "Impossible de vérifier votre licence. Vérifiez votre connexion internet puis réessayez.";
      } finally {
        this.checking = false;
      }
    },

    async recheck() {
      this.loading = true;
      await this.refreshState(true);
      this.loading = false;
    },
  };
}
