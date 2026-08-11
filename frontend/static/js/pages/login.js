function loginForm() {
  return {
    email: "",
    motDePasse: "",
    error: "",
    loading: false,
    async submit() {
      this.error = "";
      this.loading = true;
      try {
        await Api.post("/auth/login", { email: this.email, mot_de_passe: this.motDePasse });
        window.location.href = "/";
      } catch (err) {
        this.error = err.message || "Une erreur est survenue";
      } finally {
        this.loading = false;
      }
    },
  };
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const status = await Api.get("/setup/status");
    if (status.needs_setup) {
      window.location.href = "/setup";
      return;
    }
  } catch (_) {
    // en cas d'erreur réseau, on continue vers le formulaire de connexion normal
  }

  try {
    await Api.get("/auth/me");
    window.location.href = "/";
  } catch (_) {
    // Pas de session active : on reste sur la page de connexion.
  }
});
