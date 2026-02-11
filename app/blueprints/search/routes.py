from flask import Blueprint, render_template

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.get("/")
def index():
    return render_template("search/index.html")
