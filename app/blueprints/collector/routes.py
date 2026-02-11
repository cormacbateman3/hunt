from flask import Blueprint, render_template

bp = Blueprint("collector", __name__, url_prefix="/collector")


@bp.get("/")
def index():
    return render_template("collector/index.html")
