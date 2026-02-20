from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
)
from flask_login import current_user

main_views = Blueprint("main_views", __name__, static_folder="static")

@main_views.route("/")
def hello_world():
    if current_user.is_authenticated:
        return redirect(url_for("gog.dashboard"))
    else:
        return redirect(url_for("gog.login"))

@main_views.route("/home")
def home():
    return render_template("home.html")