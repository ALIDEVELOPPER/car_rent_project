async function requireAuth(activePage) {
  try {
    const user = await Api.get("/auth/me");
    renderSidebar(activePage, user);
    return user;
  } catch (err) {
    window.location.href = "/login";
    throw err;
  }
}
