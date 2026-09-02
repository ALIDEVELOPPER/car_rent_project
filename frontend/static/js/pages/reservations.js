const RESA_STATUT_BADGES = {
  en_attente: "badge-neutral",
  confirmee: "badge-info",
  en_cours: "badge-warning",
  terminee: "badge-success",
  annulee: "badge-danger",
};

function emptyReservationForm() {
  return {
    client_id: "",
    vehicule_id: "",
    date_debut: "",
    date_fin: "",
    heure_debut: "",
    heure_fin: "",
    caution: "",
    caution_statut: "non_recue",
    caution_retenue: "",
    caution_note: "",
    lieu_prise_en_charge: "",
    source: "agence",
    notes: "",
  };
}

function emptyEdl() {
  return { id: null, kilometrage: "", niveau_carburant: "", degats: "", observations: "", photos: [] };
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
    contratLoadingId: null,
    edlOpen: false,
    edlResa: null,
    edl: { depart: emptyEdl(), retour: emptyEdl() },
    edlSaving: null,

    async init() {
      this.currentUser = await requireAuth("reservations");
      await Promise.all([this.loadReservations(), this.loadClients(), this.loadVehicules()]);
    },

    statutBadgeClass(s) {
      return RESA_STATUT_BADGES[s] || "badge-neutral";
    },
    statutLabel(s) {
      return t("reservations.statut." + s) !== "reservations.statut." + s ? t("reservations.statut." + s) : s;
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

    // Véhicules proposables à la réservation : on exclut ceux en maintenance /
    // hors service, mais on garde celui déjà sélectionné (cas d'une réservation
    // existante dont le véhicule est passé hors service depuis).
    get vehiculesSelectionnables() {
      return this.vehicules.filter(
        (v) =>
          (v.statut !== "maintenance" && v.statut !== "hors_service") ||
          String(v.id) === String(this.form.vehicule_id),
      );
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
        heure_debut: r.heure_debut || "",
        heure_fin: r.heure_fin || "",
        caution: r.caution && Number(r.caution) ? r.caution : "",
        caution_statut: r.caution_statut || "non_recue",
        caution_retenue: r.caution_retenue || "",
        caution_note: r.caution_note || "",
        lieu_prise_en_charge: r.lieu_prise_en_charge || "",
        source: r.source || "agence",
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
          showToast(t("reservations.t_maj"));
        } else {
          await Api.post("/reservations", this.form);
          showToast(t("reservations.t_cree"));
        }
        this.modalOpen = false;
        await this.loadReservations();
      } catch (err) {
        this.formError = err.message;
      } finally {
        this.saving = false;
      }
    },

    async downloadContrat(reservation) {
      if (this.contratLoadingId) return;
      this.contratLoadingId = reservation.id;
      try {
        const num = String(reservation.id).padStart(5, "0");
        const result = await downloadAuthed(
          `/api/reservations/${reservation.id}/contrat/pdf`,
          `contrat-${num}.pdf`,
        );
        if (result && result.ok && window.pywebview) showToast(t("reservations.contrat_ok"));
        else if (result && result.error) showToast(result.error, "error");
      } catch (err) {
        showToast(t("common.error_generic"), "error");
      } finally {
        this.contratLoadingId = null;
      }
    },

    async openEdl(reservation) {
      this.edlResa = reservation;
      this.edl = { depart: emptyEdl(), retour: emptyEdl() };
      this.edlOpen = true;
      try {
        const etats = await Api.get(`/reservations/${reservation.id}/etats-des-lieux`);
        for (const e of etats) {
          this.edl[e.type] = {
            id: e.id,
            kilometrage: e.kilometrage ?? "",
            niveau_carburant: e.niveau_carburant || "",
            degats: e.degats || "",
            observations: e.observations || "",
            photos: e.photos || [],
          };
        }
      } catch (err) {
        showToast(err.message, "error");
      }
    },

    closeEdl() {
      this.edlOpen = false;
    },

    async saveEdl(type_) {
      this.edlSaving = type_;
      try {
        const src = this.edl[type_];
        const updated = await Api.put(
          `/reservations/${this.edlResa.id}/etats-des-lieux/${type_}`,
          {
            kilometrage: src.kilometrage === "" ? null : src.kilometrage,
            niveau_carburant: src.niveau_carburant || null,
            degats: src.degats || null,
            observations: src.observations || null,
          },
        );
        this.edl[type_] = {
          id: updated.id,
          kilometrage: updated.kilometrage ?? "",
          niveau_carburant: updated.niveau_carburant || "",
          degats: updated.degats || "",
          observations: updated.observations || "",
          photos: updated.photos || [],
        };
        showToast(t("etatdeslieux.t_saved"));
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        this.edlSaving = null;
      }
    },

    async uploadEdlPhoto(type_, fileInput) {
      const file = fileInput.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("fichier", file);
      try {
        const updated = await Api.upload(`/etat-des-lieux/${this.edl[type_].id}/photo`, formData);
        this.edl[type_].photos = updated.photos || [];
        showToast(t("etatdeslieux.t_photo"));
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        fileInput.value = "";
      }
    },

    async removeEdlPhoto(type_, url) {
      if (!confirm(t("etatdeslieux.confirm_remove_photo"))) return;
      try {
        const updated = await Api.del(`/etat-des-lieux/${this.edl[type_].id}/photo`, { url });
        this.edl[type_].photos = updated.photos || [];
        showToast(t("etatdeslieux.t_photo_removed"));
      } catch (err) {
        showToast(err.message, "error");
      }
    },

    async printEdl(type_) {
      const etatId = this.edl[type_].id;
      if (!etatId) return;
      const num = String(this.edlResa.id).padStart(5, "0");
      const result = await downloadAuthed(
        `/api/etat-des-lieux/${etatId}/pdf`,
        `etat-des-lieux-${type_}-${num}.pdf`,
      );
      if (result && result.error) showToast(result.error, "error");
    },

    async changeStatut(reservation, statut) {
      const confirmations = {
        annulee: t("reservations.confirm_annuler"),
        terminee: t("reservations.confirm_terminer"),
      };
      if (confirmations[statut] && !confirm(confirmations[statut])) return;

      try {
        await Api.patch(`/reservations/${reservation.id}/statut`, { statut });
        showToast(t("reservations.t_statut"));
        await this.loadReservations();
      } catch (err) {
        showToast(err.message, "error");
      }
    },
  };
}
