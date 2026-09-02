const JOURS_COURTS = ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"];
const JOURS_COURTS_AR = ["أحد", "إثن", "ثلا", "أرب", "خمي", "جمع", "سبت"];

function fmtMontant(v) {
  const n = Number(v);
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
}

function dashboardPage() {
  return {
    loading: true,
    data: null,
    revenus6: [],
    devise: "MAD",
    revenusAnnee: [],
    _chart: null,

    async init() {
      if (this._inited) return;
      this._inited = true;
      await requireAuth("");
      this.devise = window.currentLang && window.currentLang() === "ar" ? "درهم" : "MAD";
      try {
        this.data = await Api.get("/dashboard");
        this.revenusAnnee = this.data.revenus_annee || [];
        this.revenus6 = this.revenusAnnee.slice(-6).map((x) => Number(x.revenus));
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        this.loading = false;
      }
      this.$nextTick(() => this.renderRevenusChart());
      document.addEventListener("themechange", () => this.renderRevenusChart());
    },

    moisLabel(iso) {
      const [y, m] = iso.split("-").map(Number);
      const loc = window.currentLang && window.currentLang() === "ar" ? "ar-MA" : "fr-FR";
      return new Date(y, m - 1, 1).toLocaleDateString(loc, { month: "short" });
    },

    renderRevenusChart() {
      const ctx = document.getElementById("chart-revenus-annee");
      if (!ctx || !window.Chart || !this.revenusAnnee.length) return;
      const cs = getComputedStyle(document.querySelector(".main-content") || document.documentElement);
      const vert = cs.getPropertyValue("--c-argent").trim() || "#10b981";
      const text = cs.getPropertyValue("--color-text-muted").trim() || "#9aa1ac";
      const grid = cs.getPropertyValue("--color-border").trim() || "#eceef2";

      const g = ctx.getContext("2d").createLinearGradient(0, 0, 0, 240);
      g.addColorStop(0, vert);
      g.addColorStop(1, vert + "55");

      if (this._chart) this._chart.destroy();
      this._chart = new window.Chart(ctx, {
        type: "bar",
        data: {
          labels: this.revenusAnnee.map((x) => this.moisLabel(x.mois)),
          datasets: [
            { data: this.revenusAnnee.map((x) => Number(x.revenus)), backgroundColor: g, borderRadius: 6, maxBarThickness: 34 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (c) => `${fmtMontant(c.parsed.y)} ${this.devise}` } },
          },
          scales: {
            x: { ticks: { color: text }, grid: { display: false } },
            y: { beginAtZero: true, ticks: { color: text, callback: (v) => fmtMontant(v) }, grid: { color: grid } },
          },
        },
      });
    },

    get dateLabel() {
      if (!this.data) return "";
      const loc = window.currentLang && window.currentLang() === "ar" ? "ar-MA" : "fr-FR";
      return new Date(this.data.date + "T00:00:00").toLocaleDateString(loc, {
        weekday: "long", day: "numeric", month: "long", year: "numeric",
      });
    },

    get flotteActive() {
      const f = (this.data && this.data.flotte) || {};
      return (f.disponible || 0) + (f.loue || 0) + (f.maintenance || 0);
    },

    caPct(ca) {
      const vals = (this.data.ca_par_vehicule || []).map((v) => Number(v.ca));
      const max = Math.max(1, ...vals);
      return Math.max(3, (Number(ca) / max) * 100);
    },

    get donutSegments() {
      const f = (this.data && this.data.flotte) || {};
      const total = (f.disponible || 0) + (f.loue || 0) + (f.maintenance || 0) + (f.hors_service || 0);
      if (!total) return { total: 0, segs: [] };
      const colors = { disponible: "#4f46e5", loue: "#f59e0b", maintenance: "#94a3b8", hors_service: "#cbd5e1" };
      let offset = 25;
      const segs = ["disponible", "loue", "maintenance", "hors_service"]
        .filter((k) => f[k])
        .map((k) => {
          const pct = (f[k] / total) * 100;
          const seg = { key: k, color: colors[k], dash: `${pct.toFixed(2)} ${(100 - pct).toFixed(2)}`, offset };
          offset = (offset - pct + 100) % 100;
          return seg;
        });
      return { total, segs };
    },

    get sparkMax() {
      return Math.max(1, ...this.revenus6);
    },

    echeanceDelai(e) {
      const n = e.jours_restants;
      if (e.en_retard) return n === 0 ? t("dashboard.ech_expire_0") : t("dashboard.ech_expire_j", { n: -n });
      return n === 0 ? t("dashboard.ech_dans_0") : t("dashboard.ech_dans_j", { n });
    },

    jourCourt(iso) {
      const ar = window.currentLang && window.currentLang() === "ar";
      const d = new Date(iso + "T00:00:00");
      return (ar ? JOURS_COURTS_AR : JOURS_COURTS)[d.getDay()] + " " + d.getDate();
    },

    fmt: fmtMontant,
  };
}
