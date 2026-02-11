from flask import Blueprint, render_template

bp = Blueprint("payments", __name__, url_prefix="/payments")


@bp.get("/")
def index():
    return render_template("payments/index.html")
