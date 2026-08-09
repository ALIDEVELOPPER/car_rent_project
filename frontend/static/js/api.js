class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

const Api = (() => {
  const BASE = "/api";

  async function request(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }

    const res = await fetch(BASE + path, opts);
    const contentType = res.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await res.json().catch(() => null) : null;

    if (res.status === 401 && !path.startsWith("/auth/")) {
      window.location.href = "/login";
    }

    if (!res.ok) {
      throw new ApiError((data && data.error) || `Erreur ${res.status}`, res.status, data);
    }

    return data;
  }

  async function upload(path, formData) {
    const res = await fetch(BASE + path, { method: "POST", body: formData });
    const contentType = res.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await res.json().catch(() => null) : null;

    if (res.status === 401) {
      window.location.href = "/login";
    }
    if (!res.ok) {
      throw new ApiError((data && data.error) || `Erreur ${res.status}`, res.status, data);
    }
    return data;
  }

  return {
    get: (path) => request("GET", path),
    post: (path, body) => request("POST", path, body),
    put: (path, body) => request("PUT", path, body),
    patch: (path, body) => request("PATCH", path, body),
    del: (path) => request("DELETE", path),
    upload,
  };
})();
