// Téléchargement d'un fichier servi par une route authentifiée (session).
//
// Dans l'app desktop (pywebview) un simple lien ne déclenche pas d'enregistrement :
// on récupère donc le contenu en fetch (authentifié par le cookie de session)
// puis on le passe au process Python qui ouvre une boîte « Enregistrer sous ».
// Hors app desktop (navigateur), on retombe sur un téléchargement classique.
(function () {
  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  async function downloadAuthed(path, filename, opts) {
    opts = opts || {};
    const init = { method: opts.method || "GET" };
    if (opts.body !== undefined) {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, init);
    if (res.status === 401) {
      window.location.href = "/login";
      return { ok: false };
    }
    if (!res.ok) {
      let msg = `Erreur ${res.status}`;
      try {
        const d = await res.json();
        if (d && d.error) msg = d.error;
      } catch (e) {}
      return { ok: false, error: msg };
    }

    const blob = await res.blob();

    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_file) {
      const b64 = await blobToBase64(blob);
      const result = await window.pywebview.api.save_file(b64, filename);
      return result || { ok: false };
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    return { ok: true };
  }

  window.downloadAuthed = downloadAuthed;
})();
