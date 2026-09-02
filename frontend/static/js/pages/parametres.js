function emptyAgenceForm() {
  return { nom: "", adresse: "", telephone: "", email: "", mentions_legales: "", conditions_contrat: "", langue: "fr", ice: "", rc: "", identifiant_fiscal: "", patente: "", tva_applicable: false, taux_tva: "20" };
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
          langue: this.agence.langue || "fr",
          ice: this.agence.ice || "",
          rc: this.agence.rc || "",
          identifiant_fiscal: this.agence.identifiant_fiscal || "",
          patente: this.agence.patente || "",
          tva_applicable: !!this.agence.tva_applicable,
          taux_tva: this.agence.taux_tva || "20",
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
        showToast(t("parametres.t_agence"));
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
        showToast(t("parametres.t_logo"));
      } catch (err) {
        showToast(err.message, "error");
      }
      fileInput.value = "";
    },

    async changePassword() {
      this.passwordError = "";
      if (this.passwordForm.mot_de_passe.length < 8) {
        this.passwordError = t("parametres.password_short");
        return;
      }
      this.passwordSaving = true;
      try {
        await Api.put(`/parametres/utilisateurs/${this.currentUser.id}`, {
          mot_de_passe: this.passwordForm.mot_de_passe,
        });
        this.passwordForm.mot_de_passe = "";
        showToast(t("parametres.t_password"));
      } catch (err) {
        this.passwordError = err.message;
      } finally {
        this.passwordSaving = false;
      }
    },
  };
}
