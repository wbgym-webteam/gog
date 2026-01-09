from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
)

main_views = Blueprint("main_views", __name__, static_folder="static")

@main_views.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@main_views.route("/home")
def home():
    return render_template("home.html")