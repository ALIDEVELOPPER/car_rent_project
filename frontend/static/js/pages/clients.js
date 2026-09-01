function emptyClientForm() {
  return {
    nom: "",
    prenom: "",
    telephone: "",
    email: "",
    adresse: "",
    date_naissance: "",
    type_piece_identite: "",
    numero_piece_identite: "",
    numero_permis: "",
    date_delivrance_permis: "",
  };
}

function clientsPage() {
  return {
    clients: [],
    loading: true,
    search: "",
    searchTimeout: null,
    modalOpen: false,
    editing: null,
    form: emptyClientForm(),
    formError: "",
    saving: false,
    currentUser: null,

    async init() {
      this.currentUser = await requireAuth("clients");
      await this.loadClients();
    },

    isAdmin() {
      return this.currentUser && this.currentUser.role === "admin";
    },

    async loadClients() {
      this.loading = true;
      try {
        const qs = this.search ? `?q=${encodeURIComponent(this.search)}` : "";
        this.clients = await Api.get(`/clients${qs}`);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        this.loading = false;
      }
    },

    onSearchInput() {
      clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => this.loadClients(), 300);
    },

    openCreate() {
      this.editing = null;
      this.form = emptyClientForm();
      this.formError = "";
      this.modalOpen = true;
    },

    openEdit(client) {
      this.editing = client;
      this.form = {
        nom: client.nom,
        prenom: client.prenom,
        telephone: client.telephone,
        email: client.email || "",
        adresse: client.adresse || "",
        date_naissance: client.date_naissance || "",
        type_piece_identite: client.type_piece_identite || "",
        numero_piece_identite: client.numero_piece_identite || "",
        numero_permis: client.numero_permis || "",
        date_delivrance_permis: client.date_delivrance_permis || "",
      };
      this.formError = "";
      this.modalOpen = true;
    },

    closeModal() {
      this.modalOpen = false;
    },

    async submitForm() {
      this.formError = "";
      this.saving = true;
      const payload = { ...this.form };
      payload.date_naissance = payload.date_naissance || null;
      payload.type_piece_identite = payload.type_piece_identite || null;
      payload.date_delivrance_permis = payload.date_delivrance_permis || null;

      try {
        if (this.editing) {
          await Api.put(`/clients/${this.editing.id}`, payload);
          showToast(t("clients.t_maj"));
        } else {
          await Api.post("/clients", payload);
          showToast(t("clients.t_cree"));
        }
        this.modalOpen = false;
        await this.loadClients();
      } catch (err) {
        this.formError = err.message;
      } finally {
        this.saving = false;
      }
    },

    async deleteClient(client) {
      if (!confirm(t("clients.confirm_delete", { name: `${client.prenom} ${client.nom}` }))) return;
      try {
        await Api.del(`/clients/${client.id}`);
        showToast(t("clients.t_supprime"));
        await this.loadClients();
      } catch (err) {
        showToast(err.message, "error");
      }
    },

    async uploadDocument(client, field, fileInput) {
      const file = fileInput.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("fichier", file);
      const endpoint = field === "identite" ? "document-identite" : "permis";

      try {
        const updated = await Api.upload(`/clients/${client.id}/${endpoint}`, formData);
        showToast(t("common.document_sent"));
        Object.assign(this.editing, updated);
        const idx = this.clients.findIndex((c) => c.id === client.id);
        if (idx !== -1) this.clients[idx] = updated;
      } catch (err) {
        showToast(err.message, "error");
      }
      fileInput.value = "";
    },
  };
}
