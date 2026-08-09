from pathlib import Path

from flask import Blueprint, abort, current_app, send_from_directory
from flask_login import login_required

bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")


@bp.get("/<path:filename>")
@login_required
def get_upload(filename):
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    full_path = (upload_folder / filename).resolve()

    if not full_path.is_relative_to(upload_folder):
        abort(404)

    return send_from_directory(upload_folder, filename)
