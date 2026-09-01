function emptyAgenceForm() {
  return { nom: "", adresse: "", telephone: "", email: "", mentions_legales: "", conditions_contrat: "" };
}

function parametresPage() {
  return {
    currentUser: null,
    accessDenied: false,
    loading: true,

    agence: null,
    agenceForm: emptyAgenceForm(),
    agenceSaving: false,
    agenceError: "",

    passwordForm: { mot_de_passe: "" },
    passwordSaving: false,
    passwordError: "",

    async init() {
      this.currentUser = await requireAuth("parametres");
      if (this.currentUser.role !== "admin") {
        this.accessDenied = true;
        this.loading = false;
        return;
      }
      await this.loadAgence();
      this.loading = false;
    },

    async loadAgence() {
      try {
        this.agence = await Api.get("/parametres/agence");
        this.agenceForm = {
          nom: this.agence.nom,
          adresse: this.agence.adresse || "",
          telephone: this.agence.telephone || "",
          email: this.agence.email || "",
          mentions_legales: this.agence.mentions_legales || "",
          conditions_contrat: this.agence.conditions_contrat || "",
        };
      } catch (err) {
        showToast(err.message, "error");
      }
    },

    async saveAgence() {
      this.agenceError = "";
      this.agenceSaving = true;
      try {
        this.agence = await Api.put("/parametres/agence", this.agenceForm);
        showToast("Informations de l'agence mises à jour");
      } catch (err) {
        this.agenceError = err.message;
      } finally {
        this.agenceSaving = false;
      }
    },

    async uploadLogo(fileInput) {
      const file = fileInput.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("fichier", file);

      try {
        this.agence = await Api.upload("/parametres/agence/logo", formData);
        showToast("Logo mis à jour");
      } catch (err) {
        showToast(err.message, "error");
      }
      fileInput.value = "";
    },

    async changePassword() {
      this.passwordError = "";
      if (this.passwordForm.mot_de_passe.length < 8) {
        this.passwordError = "Le mot de passe doit contenir au moins 8 caractères";
        return;
      }
      this.passwordSaving = true;
      try {
        await Api.put(`/parametres/utilisateurs/${this.currentUser.id}`, {
          mot_de_passe: this.passwordForm.mot_de_passe,
        });
        this.passwordForm.mot_de_passe = "";
        showToast("Mot de passe modifié");
      } catch (err) {
        this.passwordError = err.message;
      } finally {
        this.passwordSaving = false;
      }
    },
  };
}
