from flask import Blueprint, render_template

bp = Blueprint("listings", __name__, url_prefix="/listings")


@bp.get("/")
def index():
    return render_template("listings/index.html")
