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

    async init() {
      if (this._inited) return;
      this._inited = true;
      await requireAuth("");
      this.devise = window.currentLang && window.currentLang() === "ar" ? "درهم" : "MAD";
      try {
        const [d, r] = await Promise.all([
          Api.get("/dashboard"),
          Api.get("/dashboard/revenus-par-mois?mois=6").catch(() => []),
        ]);
        this.data = d;
        this.revenus6 = r.map((x) => Number(x.revenus));
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        this.loading = false;
      }
    },

    get dateLabel() {
      if (!this.data) return "";
      const loc = window.currentLang && window.currentLang() === "ar" ? "ar-MA" : "fr-FR";
      return new Date(this.data.date + "T00:00:00").toLocaleDateString(loc, {
        weekday: "long", day: "numeric", month: "long", year: "numeric",
      });
    },

    // ---- flotte donut (dispo / loué / maintenance / hors service) ----
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
      return { total, segs, f };
    },

    get sparkMax() {
      return Math.max(1, ...this.revenus6);
    },

    jourCourt(iso) {
      const ar = window.currentLang && window.currentLang() === "ar";
      const d = new Date(iso + "T00:00:00");
      return (ar ? JOURS_COURTS_AR : JOURS_COURTS)[d.getDay()] + " " + d.getDate();
    },

    fmt: fmtMontant,
  };
}
