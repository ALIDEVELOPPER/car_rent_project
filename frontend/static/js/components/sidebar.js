const SIDEBAR_LINKS = [
  { key: "", label: "Tableau de bord", href: "/", icon: "home" },
  { key: "clients", label: "Clients", href: "/clients", icon: "users" },
  { key: "vehicules", label: "Véhicules", href: "/vehicules", icon: "car" },
  { key: "reservations", label: "Réservations", href: "/reservations", icon: "calendar" },
  { key: "factures", label: "Factures", href: "/factures", icon: "receipt" },
  { key: "parametres", label: "Paramètres", href: "/parametres", icon: "settings", adminOnly: true },
];

const SIDEBAR_ICONS = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>',
  users:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon"><circle cx="9" cy="8" r="3"/><path d="M2 20c0-3.3 3.1-6 7-6s7 2.7 7 6"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14c2.7.4 4.5 2.4 4.5 6"/></svg>',
  car: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon"><path d="M3 13l1.5-4.5A2 2 0 0 1 6.4 7h11.2a2 2 0 0 1 1.9 1.5L21 13"/><rect x="2" y="13" width="20" height="6" rx="1.5"/><circle cx="7" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/></svg>',
  calendar:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
  receipt:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon"><path d="M6 2h12v20l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/></svg>',
  settings:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  logout:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="icon"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>',
};

function sidebarInitials(nom) {
  return (nom || "?")
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function renderSidebar(activeKey, user) {
  const root = document.getElementById("sidebar-root");
  if (!root) return;

  const links = SIDEBAR_LINKS.filter((link) => !link.adminOnly || user.role === "admin")
    .map((link) => {
      const isActive = link.key === activeKey;
      return `<a class="sidebar-link${isActive ? " active" : ""}" href="${link.href}">${SIDEBAR_ICONS[link.icon]}<span>${link.label}</span></a>`;
    })
    .join("");

  root.innerHTML = `
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="logo-mark">AL</span>
        <span>Agence Location</span>
      </div>
      <nav class="sidebar-nav">${links}</nav>
      <div class="sidebar-footer">
        <div class="sidebar-user">
          <span class="sidebar-user-avatar">${sidebarInitials(user.nom)}</span>
          <div class="sidebar-user-info">
            <div class="sidebar-user-name">${user.nom}</div>
            <div class="sidebar-user-role">${user.role}</div>
          </div>
        </div>
        <button class="sidebar-link" id="logout-btn" type="button" style="width:100%; border:none; background:transparent; cursor:pointer;">
          ${SIDEBAR_ICONS.logout}<span>Déconnexion</span>
        </button>
      </div>
    </aside>
  `;

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      await Api.post("/auth/logout");
    } finally {
      window.location.href = "/login";
    }
  });
}
