from flask import Flask, render_template, request, redirect, url_for, Blueprint, current_app, flash, session
from . import db
from .models import Game, Teams, GamePoints, Log, TeamType, User, DependencyType, ScoringPreference
from sqlalchemy import func
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
import sqlite3
from datetime import datetime

gog = Blueprint("gog", __name__)
DATABASE = "wbgym.db"

def calculate_ranked_points(game_id):   
    game = Game.query.get(game_id)

    # Separate rankings for A Teams and B Teams
    for team_type in [TeamType.A, TeamType.B]:
        game_points = GamePoints.query\
            .join(Teams)\
            .filter(Teams.team_type == team_type)\
            .filter(GamePoints.game_id == game_id)\
            .all()

        # Sort based on game's scoring preference
        if game.scoring_preference == ScoringPreference.LOWER:
            game_points.sort(key=lambda x: x.points)  # Lower is better
        else:
            game_points.sort(key=lambda x: x.points, reverse=True)  # Higher is better

        # Assign ranks
        for position, game_point in enumerate(game_points, start=1):
            game_point.final_points = position
            db.session.add(game_point)

            log_entry = Log.query.filter_by(team_id=game_point.team_id, game_id=game_point.game_id).first()
            if log_entry:
                log_entry.points = game_point.points
            else:
                log_entry = Log(team_id=game_point.team_id, game_id=game_point.game_id, points=game_point.points)
            db.session.add(log_entry)
    
    db.session.commit()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def regular_user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_administrator:
            flash("Please login with a regular user account to access this area.")
            return redirect(url_for('gog.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_rankings(): #detirmes the final ranking of the each team
    """
    Returns a dictionary with game IDs as keys and game data (including A and B team rankings) as values.
    """
    rankings = {}
    games = Game.query.all()
    
    for game in games:
        # Get all points for this game
        game_points = GamePoints.query\
            .join(Teams)\
            .filter(GamePoints.game_id == game.id)\
            .all()
        
        a_teams = [p for p in game_points if p.team.team_type == TeamType.A]
        b_teams = [p for p in game_points if p.team.team_type == TeamType.B]
        
        rankings[game.id] = {
            'name': game.name,
            'A_teams': a_teams,
            'B_teams': b_teams
        }
    
    return rankings

@gog.route("/") #redirects user to default page
def redirectToLogin():
    return redirect("/gog/login")

@gog.route("/login", methods=["GET", "POST"]) #default page, if user is not logged in
def login():
    # Clear any existing flash messages when arriving at login page
    session.pop('_flashes', None)
    
    if request.method == "POST":    #verifies the user login
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username, is_admin=False).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("gog.dashboard")) #if true credential, do this
        else:
            flash('Falscher Benutzername/Passwort') #if false credential, do this
            return render_template("gog/gog_login.html")

    return render_template("gog/gog_login.html")    #default template, when accessing this route

@gog.route("/dashboard") #default page, when logged in
@login_required
@regular_user_required
def dashboard():
    return render_template("gog/gog_dashboard.html")    #default template, when accessing this route

@gog.route("/setup", methods=["GET", "POST"]) #determines page, where you change the team name, by picking the team id, and modifying the team name
@login_required
@regular_user_required
def setup():
    if request.method == "POST":
        team_id = request.form.get("team_id")
        team_name = request.form.get("team_name")
        
        if not team_id or not team_name:
            flash("Please fill in all fields")
            return redirect(url_for("gog.setup"))
        
        team = Teams.query.get(team_id)
        if not team:
            flash("Ungültiges Team ausgewählt")
            return redirect(url_for("gog.setup"))
        
        try:
            team.team_name = team_name
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Aktualisieren des Teamnamens: {str(e)}')
            return redirect(url_for("gog.setup"))
        
        return redirect(url_for("gog.dashboard"))

    teams = Teams.query.all()
    return render_template("gog/gog_setup.html", teams=teams)

@gog.route("/teamManagement", methods=["GET", "POST"]) #determines page, where you can manage and give the team points
@login_required
@regular_user_required
def teamManagement():
    if request.method == "POST":
        team_id = request.form.get("team_id")
        game_id = request.form.get("game_id")
        score = request.form.get("score")

        if not all([team_id, game_id, score]):
            flash("Please fill in all fields")
            return redirect(url_for("gog.teamManagement"))

        try:
            game_id = int(game_id)
            score = int(score)
            
            game = Game.query.get(game_id)
            if not game:
                flash("Invalid game selected")
                return redirect(url_for("gog.teamManagement"))
            
            # Check if team already has a score for this game
            existing_score = GamePoints.query.filter_by(
                team_id=team_id,
                game_id=game_id
            ).first()

            if existing_score:
                existing_score.points = score
            else:
                game_point = GamePoints(team_id=team_id, game_id=game_id, points=score)
                db.session.add(game_point)

            # Create or update log entry
            log = Log(
                team_id=team_id,
                game_id=game_id,
                points=score,
                user_id=current_user.id,
                timestamp=datetime.utcnow()
            )
            db.session.add(log)
            
            db.session.commit()
            calculate_ranked_points(game_id)
            return redirect(url_for("gog.dashboard"))  # Changed to redirect to dashboard
            
        except ValueError:
            flash("Invalid score format")
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording score: {str(e)}')
        
        return redirect(url_for("gog.teamManagement"))

    teams = Teams.query.all()
    games = Game.query.all()
    game_points = GamePoints.query.all()
    
    return render_template(
        "gog/gog_teamManagement.html",
        teams=teams,
        games=games,
        game_points=game_points
    )

@gog.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('gog.login'))

