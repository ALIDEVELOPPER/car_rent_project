async function requireAuth(activePage) {
  try {
    const user = await Api.get("/auth/me");
    let agence = null;
    try {
      agence = await Api.get("/parametres/agence");
    } catch (e) {}
    renderSidebar(activePage, user, agence);
    return user;
  } catch (err) {
    window.location.href = "/login";
    throw err;
  }
}
