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
          window.t("licence.reason." + state.reason) !== "licence.reason." + state.reason
            ? window.t("licence.reason." + state.reason)
            : window.t("licence.reason.generic");
        const parts = [];
        if (state.contact_email) parts.push(state.contact_email);
        if (state.contact_phone) parts.push(state.contact_phone);
        this.contact = parts.join("  ·  ");
      } catch (err) {
        this.blockedMessage = window.t("licence.reason.network");
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
