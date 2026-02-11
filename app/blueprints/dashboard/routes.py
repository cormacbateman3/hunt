from flask import Blueprint, render_template

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.get("/")
def index():
    return render_template("dashboard/index.html")
