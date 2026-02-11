from flask import Blueprint, render_template

bp = Blueprint("stories", __name__, url_prefix="/stories")


@bp.get("/")
def index():
    return render_template("stories/index.html")
