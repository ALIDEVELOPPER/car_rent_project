function setupForm() {
  return {
    nom: "",
    email: "",
    motDePasse: "",
    motDePasseConfirm: "",
    error: "",
    loading: false,
    async submit() {
      this.error = "";

      if (this.motDePasse !== this.motDePasseConfirm) {
        this.error = window.t("setup.mismatch");
        return;
      }

      this.loading = true;
      try {
        await Api.post("/setup/admin", {
          nom: this.nom,
          email: this.email,
          mot_de_passe: this.motDePasse,
        });
        window.location.href = "/login";
      } catch (err) {
        this.error = err.message || window.t("common.error_generic");
      } finally {
        this.loading = false;
      }
    },
  };
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const status = await Api.get("/setup/status");
    if (!status.needs_setup) {
      window.location.href = "/login";
    }
  } catch (_) {
    // en cas d'erreur réseau, on laisse l'utilisateur sur l'écran de configuration
  }
});
