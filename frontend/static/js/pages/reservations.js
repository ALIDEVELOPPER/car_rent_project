const RESA_STATUT_BADGES = {
  en_attente: "badge-neutral",
  confirmee: "badge-info",
  en_cours: "badge-warning",
  terminee: "badge-success",
  annulee: "badge-danger",
};

const RESA_STATUT_LABELS = {
  en_attente: "En attente",
  confirmee: "Confirmée",
  en_cours: "En cours",
  terminee: "Terminée",
  annulee: "Annulée",
};

function emptyReservationForm() {
  return { client_id: "", vehicule_id: "", date_debut: "", date_fin: "", notes: "" };
}

function reservationsPage() {
  return {
    reservations: [],
    clients: [],
    vehicules: [],
    loading: true,
    statutFilter: "",
    modalOpen: false,
    editing: null,
    form: emptyReservationForm(),
    formError: "",
    saving: false,
    dispoStatus: null,
    dispoTimeout: null,
    currentUser: null,

    async init() {
      this.currentUser = await requireAuth("reservations");
      await Promise.all([this.loadReservations(), this.loadClients(), this.loadVehicules()]);
    },

    statutBadgeClass(s) {
      return RESA_STATUT_BADGES[s] || "badge-neutral";
    },
    statutLabel(s) {
      return RESA_STATUT_LABELS[s] || s;
    },

    clientLabel(id) {
      const c = this.clients.find((c) => c.id === id);
      return c ? `${c.prenom} ${c.nom}` : `#${id}`;
    },
    vehiculeLabel(id) {
      const v = this.vehicules.find((v) => v.id === id);
      return v ? `${v.marque} ${v.modele} (${v.immatriculation})` : `#${id}`;
    },

    async loadReservations() {
      this.loading = true;
      try {
        const qs = this.statutFilter ? `?statut=${this.statutFilter}` : "";
        this.reservations = await Api.get(`/reservations${qs}`);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        this.loading = false;
      }
    },

    async loadClients() {
      this.clients = await Api.get("/clients");
    },

    async loadVehicules() {
      this.vehicules = await Api.get("/vehicules");
    },

    openCreate() {
      this.editing = null;
      this.form = emptyReservationForm();
      this.formError = "";
      this.dispoStatus = null;
      this.modalOpen = true;
    },

    openEdit(r) {
      this.editing = r;
      this.form = {
        client_id: r.client_id,
        vehicule_id: r.vehicule_id,
        date_debut: r.date_debut,
        date_fin: r.date_fin,
        notes: r.notes || "",
      };
      this.formError = "";
      this.dispoStatus = null;
      this.modalOpen = true;
      this.checkDisponibilite();
    },

    closeModal() {
      this.modalOpen = false;
    },

    estimate() {
      const vehicule = this.vehicules.find((v) => v.id === Number(this.form.vehicule_id));
      if (!vehicule || !this.form.date_debut || !this.form.date_fin) return null;

      const debut = new Date(this.form.date_debut);
      const fin = new Date(this.form.date_fin);
      const jours = Math.round((fin - debut) / 86400000);
      if (jours <= 0) return null;

      return { jours, tarifJour: vehicule.tarif_jour, montant: (Number(vehicule.tarif_jour) * jours).toFixed(2) };
    },

    onAvailabilityInputsChanged() {
      clearTimeout(this.dispoTimeout);
      this.dispoTimeout = setTimeout(() => this.checkDisponibilite(), 250);
    },

    async checkDisponibilite() {
      this.dispoStatus = null;
      if (!this.form.vehicule_id || !this.form.date_debut || !this.form.date_fin) return;
      if (this.form.date_fin <= this.form.date_debut) {
        this.dispoStatus = "invalid";
        return;
      }

      this.dispoStatus = "checking";
      try {
        const params = new URLSearchParams({ date_debut: this.form.date_debut, date_fin: this.form.date_fin });
        if (this.editing) params.set("exclude_reservation_id", this.editing.id);
        const res = await Api.get(`/vehicules/${this.form.vehicule_id}/disponibilite?${params}`);
        this.dispoStatus = res.disponible ? "disponible" : "indisponible";
      } catch (err) {
        this.dispoStatus = null;
      }
    },

    submitDisabled() {
      return this.saving || ["indisponible", "invalid", "checking"].includes(this.dispoStatus);
    },

    async submitForm() {
      this.formError = "";
      this.saving = true;
      try {
        if (this.editing) {
          await Api.put(`/reservations/${this.editing.id}`, this.form);
          showToast("Réservation mise à jour");
        } else {
          await Api.post("/reservations", this.form);
          showToast("Réservation créée");
        }
        this.modalOpen = false;
        await this.loadReservations();
      } catch (err) {
        this.formError = err.message;
      } finally {
        this.saving = false;
      }
    },

    async changeStatut(reservation, statut) {
      const confirmations = {
        annulee: "Annuler cette réservation ?",
        terminee: "Clôturer cette réservation ? Une facture sera générée automatiquement.",
      };
      if (confirmations[statut] && !confirm(confirmations[statut])) return;

      try {
        await Api.patch(`/reservations/${reservation.id}/statut`, { statut });
        showToast("Statut mis à jour");
        await this.loadReservations();
      } catch (err) {
        showToast(err.message, "error");
      }
    },
  };
}
