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
    await Api.get("/auth/me");
    window.location.href = "/";
  } catch (_) {
    // Pas de session active : on reste sur la page de connexion.
  }
});
