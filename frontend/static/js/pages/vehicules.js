const STATUT_BADGES = {
  disponible: "badge-success",
  loue: "badge-info",
  maintenance: "badge-warning",
  hors_service: "badge-danger",
};

const STATUT_LABELS = {
  disponible: "Disponible",
  loue: "Loué",
  maintenance: "Maintenance",
  hors_service: "Hors service",
};

function emptyVehiculeForm() {
  return {
    marque: "",
    modele: "",
    immatriculation: "",
    categorie: "",
    annee: "",
    couleur: "",
    kilometrage: "",
    carburant: "",
    transmission: "",
    tarif_jour: "",
    statut: "disponible",
  };
}

function vehiculesPage() {
  return {
    vehicules: [],
    loading: true,
    search: "",
    statutFilter: "",
    searchTimeout: null,
    modalOpen: false,
    editing: null,
    form: emptyVehiculeForm(),
    formError: "",
    saving: false,
    currentUser: null,

    async init() {
      this.currentUser = await requireAuth("vehicules");
      await this.loadVehicules();
    },

    isAdmin() {
      return this.currentUser && this.currentUser.role === "admin";
    },

    statutBadgeClass(statut) {
      return STATUT_BADGES[statut] || "badge-neutral";
    },

    statutLabel(statut) {
      return STATUT_LABELS[statut] || statut;
    },

    async loadVehicules() {
      this.loading = true;
      try {
        const params = new URLSearchParams();
        if (this.search) params.set("q", this.search);
        if (this.statutFilter) params.set("statut", this.statutFilter);
        const qs = params.toString() ? `?${params}` : "";
        this.vehicules = await Api.get(`/vehicules${qs}`);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        this.loading = false;
      }
    },

    onSearchInput() {
      clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => this.loadVehicules(), 300);
    },

    openCreate() {
      this.editing = null;
      this.form = emptyVehiculeForm();
      this.formError = "";
      this.modalOpen = true;
    },

    openEdit(vehicule) {
      this.editing = vehicule;
      this.form = {
        marque: vehicule.marque,
        modele: vehicule.modele,
        immatriculation: vehicule.immatriculation,
        categorie: vehicule.categorie,
        annee: vehicule.annee || "",
        couleur: vehicule.couleur || "",
        kilometrage: vehicule.kilometrage ?? "",
        carburant: vehicule.carburant || "",
        transmission: vehicule.transmission || "",
        tarif_jour: vehicule.tarif_jour,
        statut: vehicule.statut,
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
      payload.annee = payload.annee !== "" ? Number(payload.annee) : null;
      payload.kilometrage = payload.kilometrage !== "" ? Number(payload.kilometrage) : null;
      payload.carburant = payload.carburant || null;
      payload.transmission = payload.transmission || null;

      try {
        if (this.editing) {
          await Api.put(`/vehicules/${this.editing.id}`, payload);
          showToast("Véhicule mis à jour");
        } else {
          await Api.post("/vehicules", payload);
          showToast("Véhicule créé");
        }
        this.modalOpen = false;
        await this.loadVehicules();
      } catch (err) {
        this.formError = err.message;
      } finally {
        this.saving = false;
      }
    },

    async deleteVehicule(vehicule) {
      if (!confirm(`Supprimer ${vehicule.marque} ${vehicule.modele} (${vehicule.immatriculation}) ?`)) return;
      try {
        await Api.del(`/vehicules/${vehicule.id}`);
        showToast("Véhicule supprimé");
        await this.loadVehicules();
      } catch (err) {
        showToast(err.message, "error");
      }
    },

    async uploadPhoto(vehicule, fileInput) {
      const file = fileInput.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("fichier", file);

      try {
        const updated = await Api.upload(`/vehicules/${vehicule.id}/photo`, formData);
        showToast("Photo envoyée");
        Object.assign(this.editing, updated);
        const idx = this.vehicules.findIndex((v) => v.id === vehicule.id);
        if (idx !== -1) this.vehicules[idx] = updated;
      } catch (err) {
        showToast(err.message, "error");
      }
      fileInput.value = "";
    },
  };
}
