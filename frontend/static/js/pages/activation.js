const BLOCKED_MESSAGES = {
  essai_expire: "Votre période d'essai de 7 jours est terminée. Contactez-nous pour activer votre compte.",
  suspendu: "Votre compte a été suspendu. Contactez-nous pour plus d'informations.",
  verification_impossible: "Impossible de vérifier votre abonnement. Connectez-vous à internet puis réessayez.",
};

function activationPage() {
  return {
    checking: true,
    needsActivation: false,
    blockedMessage: "",
    code: "",
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
        this.needsActivation = !state.activated;
        this.blockedMessage = BLOCKED_MESSAGES[state.reason] || "Votre accès est actuellement bloqué. Contactez-nous.";
      } catch (err) {
        this.needsActivation = true;
        this.error = "";
      } finally {
        this.checking = false;
      }
    },

    async submit() {
      this.error = "";
      this.loading = true;
      try {
        await Api.post("/licence/activate", { code: this.code });
        window.location.href = "/";
      } catch (err) {
        this.error = err.message || "Une erreur est survenue";
      } finally {
        this.loading = false;
      }
    },

    async recheck() {
      this.loading = true;
      await this.refreshState(true);
      this.loading = false;
    },
  };
}
