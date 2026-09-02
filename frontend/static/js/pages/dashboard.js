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
      await this.refresh();
      this.loading = false;
      this.$nextTick(() => this.renderRevenusChart());
      document.addEventListener("themechange", () => this.renderRevenusChart());
      // Le tableau de bord se rafraîchit tout seul (l'agence garde la page ouverte
      // toute la journée) ; se met en pause quand l'onglet n'est pas visible.
      setInterval(() => {
        if (!document.hidden) this.refresh();
      }, 60000);
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) this.refresh();
      });
    },

    async refresh() {
      try {
        const fresh = await Api.get("/dashboard");
        this.data = fresh;
        this.revenusAnnee = fresh.revenus_annee || [];
        this.revenus6 = this.revenusAnnee.slice(-6).map((x) => Number(x.revenus));
        if (!this.loading) this.$nextTick(() => this.renderRevenusChart());
      } catch (err) {
        if (this.loading) showToast(err.message, "error");
      }
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
            y: { beginAtZero: true, ticks: { precision: 0, color: text, callback: (v) => fmtMontant(v) }, grid: { color: grid } },
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

    margePct(marge) {
      const vals = (this.data.rentabilite || []).map((v) => Math.abs(Number(v.marge)));
      const max = Math.max(1, ...vals);
      return Math.max(3, (Math.abs(Number(marge)) / max) * 100);
    },

    // Répartition de la flotte (dispo / loué / maintenance / hors service).
    // Un simple conic-gradient — pas de <template> dans du SVG (Alpine ne sait
    // pas cloner un <template> en espace de noms SVG et plante toute la page).
    get flotte() {
      const f = (this.data && this.data.flotte) || {};
      const colors = { disponible: "#4f46e5", loue: "#f59e0b", maintenance: "#eab308", hors_service: "#94a3b8" };
      const keys = ["disponible", "loue", "maintenance", "hors_service"];
      const total = keys.reduce((s, k) => s + (f[k] || 0), 0);
      const segments = keys.map((k) => ({
        key: k,
        color: colors[k],
        n: f[k] || 0,
        pct: total ? Math.round(((f[k] || 0) / total) * 100) : 0,
      }));
      return { total, segments };
    },

    get donutStyle() {
      const { total, segments } = this.flotte;
      if (!total) return "background: var(--color-neutral-bg);";
      let acc = 0;
      const stops = [];
      for (const s of segments) {
        if (!s.n) continue;
        const start = (acc / total) * 100;
        acc += s.n;
        const end = (acc / total) * 100;
        stops.push(`${s.color} ${start.toFixed(2)}% ${end.toFixed(2)}%`);
      }
      return `background: conic-gradient(${stops.join(", ")});`;
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
