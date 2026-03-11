from flask import Blueprint, render_template, request, redirect, session

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pass
    else:
        return render_template("login.html")
