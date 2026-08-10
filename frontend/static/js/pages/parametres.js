function emptyAgenceForm() {
  return { nom: "", adresse: "", telephone: "", email: "", mentions_legales: "" };
}

function emptyUserForm() {
  return { nom: "", email: "", mot_de_passe: "", role: "employe" };
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

    users: [],
    userModalOpen: false,
    editingUser: null,
    userForm: emptyUserForm(),
    userError: "",
    userSaving: false,

    async init() {
      this.currentUser = await requireAuth("parametres");
      if (this.currentUser.role !== "admin") {
        this.accessDenied = true;
        this.loading = false;
        return;
      }
      await Promise.all([this.loadAgence(), this.loadUsers()]);
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

    async loadUsers() {
      try {
        this.users = await Api.get("/parametres/utilisateurs");
      } catch (err) {
        showToast(err.message, "error");
      }
    },

    isSelf(user) {
      return this.currentUser && user.id === this.currentUser.id;
    },

    openCreateUser() {
      this.editingUser = null;
      this.userForm = emptyUserForm();
      this.userError = "";
      this.userModalOpen = true;
    },

    openEditUser(user) {
      this.editingUser = user;
      this.userForm = { nom: user.nom, email: user.email, mot_de_passe: "", role: user.role };
      this.userError = "";
      this.userModalOpen = true;
    },

    closeUserModal() {
      this.userModalOpen = false;
    },

    async submitUserForm() {
      this.userError = "";
      this.userSaving = true;
      const payload = { ...this.userForm };
      if (!payload.mot_de_passe) delete payload.mot_de_passe;

      try {
        if (this.editingUser) {
          await Api.put(`/parametres/utilisateurs/${this.editingUser.id}`, payload);
          showToast("Utilisateur mis à jour");
        } else {
          await Api.post("/parametres/utilisateurs", payload);
          showToast("Utilisateur créé");
        }
        this.userModalOpen = false;
        await this.loadUsers();
      } catch (err) {
        this.userError = err.message;
      } finally {
        this.userSaving = false;
      }
    },

    async toggleActif(user) {
      try {
        await Api.patch(`/parametres/utilisateurs/${user.id}/actif`, { actif: !user.actif });
        showToast(user.actif ? "Utilisateur désactivé" : "Utilisateur activé");
        await this.loadUsers();
      } catch (err) {
        showToast(err.message, "error");
      }
    },

    async deleteUser(user) {
      if (!confirm(`Supprimer ${user.nom} ?`)) return;
      try {
        await Api.del(`/parametres/utilisateurs/${user.id}`);
        showToast("Utilisateur supprimé");
        await this.loadUsers();
      } catch (err) {
        showToast(err.message, "error");
      }
    },
  };
}
