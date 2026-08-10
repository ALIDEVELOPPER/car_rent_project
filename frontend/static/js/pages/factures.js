const FACTURE_STATUT_BADGES = {
  en_attente: "badge-warning",
  payee: "badge-success",
  annulee: "badge-danger",
};

const FACTURE_STATUT_LABELS = {
  en_attente: "En attente",
  payee: "Payée",
  annulee: "Annulée",
};

const MODE_PAIEMENT_LABELS = {
  especes: "Espèces",
  carte: "Carte",
  virement: "Virement",
  cheque: "Chèque",
};

function facturesPage() {
  return {
    factures: [],
    loading: true,
    search: "",
    statutFilter: "",
    searchTimeout: null,
    paiementModalOpen: false,
    payingFacture: null,
    modePaiement: "",
    paiementError: "",
    saving: false,
    currentUser: null,

    async init() {
      this.currentUser = await requireAuth("factures");
      await this.loadFactures();
    },

    statutBadgeClass(s) {
      return FACTURE_STATUT_BADGES[s] || "badge-neutral";
    },
    statutLabel(s) {
      return FACTURE_STATUT_LABELS[s] || s;
    },
    modeLabel(m) {
      return MODE_PAIEMENT_LABELS[m] || m;
    },

    async loadFactures() {
      this.loading = true;
      try {
        const params = new URLSearchParams();
        if (this.search) params.set("q", this.search);
        if (this.statutFilter) params.set("statut_paiement", this.statutFilter);
        const qs = params.toString() ? `?${params}` : "";
        this.factures = await Api.get(`/factures${qs}`);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        this.loading = false;
      }
    },

    onSearchInput() {
      clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => this.loadFactures(), 300);
    },

    openPaiementModal(facture) {
      this.payingFacture = facture;
      this.modePaiement = "";
      this.paiementError = "";
      this.paiementModalOpen = true;
    },

    closePaiementModal() {
      this.paiementModalOpen = false;
    },

    async confirmPaiement() {
      this.paiementError = "";
      if (!this.modePaiement) {
        this.paiementError = "Sélectionnez un mode de paiement";
        return;
      }
      this.saving = true;
      try {
        await Api.patch(`/factures/${this.payingFacture.id}/statut-paiement`, {
          statut_paiement: "payee",
          mode_paiement: this.modePaiement,
        });
        showToast("Facture marquée comme payée");
        this.paiementModalOpen = false;
        await this.loadFactures();
      } catch (err) {
        this.paiementError = err.message;
      } finally {
        this.saving = false;
      }
    },

    async annulerFacture(facture) {
      if (!confirm(`Annuler la facture ${facture.numero_facture} ?`)) return;
      try {
        await Api.patch(`/factures/${facture.id}/statut-paiement`, { statut_paiement: "annulee" });
        showToast("Facture annulée");
        await this.loadFactures();
      } catch (err) {
        showToast(err.message, "error");
      }
    },
  };
}
