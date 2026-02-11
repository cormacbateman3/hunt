from flask import Blueprint, render_template

bp = Blueprint("bids", __name__, url_prefix="/bids")


@bp.get("/")
def index():
    return render_template("bids/index.html")
