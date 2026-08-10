let revenusChart = null;
let topVehiculesChart = null;

function chartColors() {
  const styles = getComputedStyle(document.documentElement);
  return {
    text: styles.getPropertyValue("--color-text-secondary").trim(),
    grid: styles.getPropertyValue("--color-border").trim(),
    primary: styles.getPropertyValue("--color-primary").trim(),
    success: styles.getPropertyValue("--color-success").trim(),
  };
}

function formatMontant(value) {
  return `${Number(value).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`;
}

async function loadKpis() {
  const kpis = await Api.get("/dashboard/kpis");
  document.getElementById("kpi-taux-occupation").textContent = `${kpis.taux_occupation}%`;
  document.getElementById("kpi-revenus-mois").textContent = formatMontant(kpis.revenus_du_mois);
  document.getElementById("kpi-vehicules-disponibles").textContent = kpis.vehicules_disponibles;
  document.getElementById("kpi-reservations-en-cours").textContent = kpis.reservations_en_cours;
}

async function loadRevenusChart() {
  const data = await Api.get("/dashboard/revenus-par-mois?mois=12");
  const colors = chartColors();
  const ctx = document.getElementById("chart-revenus");
  if (!ctx) return;

  if (revenusChart) revenusChart.destroy();
  revenusChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((d) => d.mois),
      datasets: [
        {
          label: "Revenus (MAD)",
          data: data.map((d) => Number(d.revenus)),
          borderColor: colors.primary,
          backgroundColor: `${colors.primary}33`,
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: colors.text }, grid: { color: colors.grid } },
        y: { ticks: { color: colors.text }, grid: { color: colors.grid }, beginAtZero: true },
      },
    },
  });
}

async function loadTopVehiculesChart() {
  const data = await Api.get("/dashboard/top-vehicules?limit=5");
  const container = document.getElementById("top-vehicules-container");
  if (!container) return;

  if (data.length === 0) {
    if (topVehiculesChart) {
      topVehiculesChart.destroy();
      topVehiculesChart = null;
    }
    container.innerHTML = '<p class="empty-state">Aucune réservation enregistrée pour le moment.</p>';
    return;
  }

  if (!document.getElementById("chart-top-vehicules")) {
    container.innerHTML = '<canvas id="chart-top-vehicules" height="120"></canvas>';
  }

  const colors = chartColors();
  const ctx = document.getElementById("chart-top-vehicules");

  if (topVehiculesChart) topVehiculesChart.destroy();
  topVehiculesChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((v) => `${v.marque} ${v.modele}`),
      datasets: [
        {
          label: "Réservations",
          data: data.map((v) => v.nombre_reservations),
          backgroundColor: colors.success,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: colors.text, precision: 0 }, grid: { color: colors.grid }, beginAtZero: true },
        y: { ticks: { color: colors.text }, grid: { display: false } },
      },
    },
  });
}

async function loadDashboard() {
  await Promise.all([loadKpis(), loadRevenusChart(), loadTopVehiculesChart()]);
}

document.addEventListener("DOMContentLoaded", async () => {
  await requireAuth("");
  await loadDashboard();
});

document.addEventListener("themechange", () => {
  loadRevenusChart();
  loadTopVehiculesChart();
});
