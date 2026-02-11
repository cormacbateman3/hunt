from flask import Blueprint, render_template

bp = Blueprint("education", __name__, url_prefix="/education")


@bp.get("/")
def index():
    return render_template("education/index.html")
