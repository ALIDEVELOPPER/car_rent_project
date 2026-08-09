import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage

ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class UploadError(ValueError):
    pass


def save_upload(file: FileStorage | None, subdir: str, allowed_extensions: set[str] = ALLOWED_DOCUMENT_EXTENSIONS) -> str:
    if file is None or not file.filename:
        raise UploadError("Aucun fichier fourni")

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in allowed_extensions:
        raise UploadError(f"Extension non autorisée : .{extension}")

    filename = f"{uuid.uuid4().hex}.{extension}"
    target_dir = Path(current_app.config["UPLOAD_FOLDER"]) / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    file.save(target_dir / filename)

    return f"{subdir}/{filename}"
