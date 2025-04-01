from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from functools import wraps
from .models import User, Teams, TeamType, Game, DependencyType, ScoringPreference, Admin, GamePoints, Log, db
import logging
from sqlalchemy import func

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__, 
                 url_prefix='/gog/admin', 
                 template_folder='templates/gog',  # Updated template folder path
                 static_folder='static/gog/admin',
                 static_url_path='/static/admin')

def admin_required(f):  
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Please login as admin to access this area.', 'admin')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin.before_request
def check_admin():
    # Skip authentication for static files and login route
    if not request.endpoint:
        return
    
    if 'static' in request.endpoint or request.endpoint == 'admin.login':
        return

    # Check if user is authenticated and is admin
    if not current_user.is_authenticated or not session.get('is_admin'):
        session.clear()  # Clear any existing session
        return redirect(url_for('admin.login'))

#defines the login page for the admin, which is the "default page" if not authenticated
@admin.route('/login', methods=['GET', 'POST'])
def login():
    # Clear any existing session
    if 'is_admin' in session and not current_user.is_authenticated:
        session.clear()
    
    # If user is already authenticated and is admin, redirect to dashboard
    if current_user.is_authenticated and session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST': #detirmines what has to go in the login page
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()  # Check if user exists
        
        if user and user.check_password(password) and user.is_admin:    #if user is admin, do this
            login_user(user)
            session['is_admin'] = True
            session['user_id'] = user.id
            session.permanent = True
            return redirect(url_for('admin.dashboard'))
        
        flash('Falscher Benutzername/Passwort')
        return render_template('gog/admin/login.html')
    
    return render_template('gog/admin/login.html')

@admin.route('/logout')
@admin_required
def logout():
    session.clear()
    return redirect(url_for('admin.login'))

#serves as the "default page" for the admin, if authenticated
@admin.route('/dashboard')
@login_required
@admin_required
def dashboard():
    if not current_user.is_authenticated or not session.get('is_admin'):    #if not authenticated, redirect to login
        return redirect(url_for('admin.login'))
    
    users = User.query.filter_by(is_admin=False).all() #lists all regular users
    admins = Admin.query.all() #lists all admin users, but currently not integrated into the templates!!! (18.2.2025)
    teams = Teams.query.all() #lists all teams
    games = Game.query.all() #lists all games
    return render_template('gog/admin/dashboard.html', users=users, teams=teams, games=games, admins=admins)

#creates the form for creating a new regular users account
@admin.route('/users/create', methods=['GET'])
@admin_required
def create_user_form():
    return render_template('gog/admin/create_user.html')

@admin.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    username = request.form['username']
    password = request.form['password']
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists!')
        return redirect(url_for('admin.dashboard'))
    
    user = User(username=username, is_admin=False)  # Explicitly set is_admin to False
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    flash('User created successfully!')
    return redirect(url_for('admin.dashboard'))

#setup for deleting a regular users account
@admin.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully!')
    return redirect(url_for('admin.dashboard'))

#page for creating a new team
@admin.route('/teams/create', methods=['GET'])
@admin_required
def create_team_form():
    return render_template('gog/admin/create_team.html')

@admin.route('/teams/create', methods=['POST'])
@admin_required
def create_team():
    # this the team consists of
    name = request.form['name']
    type_id = request.form['type']
    number = request.form['number']
    
    team_id = f"{type_id.lower()}{number}"
    
    if Teams.query.filter_by(id=team_id).first(): #checks if team already exists
        flash('Team already exists!')
        return redirect(url_for('admin.dashboard'))
    
    if not name:
        name = team_id
    
    team = Teams(team_type=type_id, team_number=number)
    team.id = team_id
    team.team_name = name
    db.session.add(team)
    db.session.commit()
    
    flash('Team created successfully!')
    return redirect(url_for('admin.dashboard'))

#page/function for deleting a team
@admin.route('/teams/delete/<string:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    try:
        # Get the team
        team = Teams.query.get_or_404(team_id)
        logger.info(f"Found team to delete: {team.id}")
        
        # First delete all related game points
        points_deleted = GamePoints.query.filter_by(team_id=team_id).delete()
        logger.info(f"Deleted {points_deleted} game points records")
        
        # Delete all related logs
        logs_deleted = Log.query.filter_by(team_id=team_id).delete()
        logger.info(f"Deleted {logs_deleted} log records")
        
        # Now delete the team
        db.session.delete(team)
        db.session.commit()
        
        logger.info(f"Successfully deleted team {team_id}")
        flash('Team deleted successfully!')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting team {team_id}: {str(e)}")
        flash(f'Error deleting team: {str(e)}')
        
    return redirect(url_for('admin.dashboard'))

#page for creating a new game
@admin.route('/games/create', methods=['GET'])
@admin_required
def create_game_form():
    # Clear any existing flash messages when loading the form
    session.pop('_flashes', None)
    return render_template('gog/admin/create_game.html')

@admin.route('/games/create', methods=['POST'])
@admin_required
def create_game():
    name = request.form['name']
    dependency_type = request.form.get('dependency_type')
    scoring_pref = request.form.get('scoring_preference')
    
    if Game.query.filter_by(name=name).first():
        flash('Game already exists!')
        return redirect(url_for('admin.dashboard'))
    
    # Validate the values
    if not dependency_type in ['point', 'time']:
        flash('Invalid dependency type!', 'admin')
        return redirect(url_for('admin.create_game_form'))
        
    # Convert string to enum
    try:
        scoring_preference = ScoringPreference(scoring_pref)
    except ValueError:
        flash('Invalid scoring preference!', 'admin')
        return redirect(url_for('admin.create_game_form'))
    
    game = Game(
        name=name,
        dependency_type=dependency_type,
        scoring_preference=scoring_preference  # Pass enum directly
    )
    
    try:
        db.session.add(game)
        db.session.commit()
        flash('Game created successfully!', 'admin')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating game: {str(e)}', 'admin')
        return redirect(url_for('admin.create_game_form'))
    
    return redirect(url_for('admin.dashboard'))

#function for deleting a game
@admin.route('/games/delete/<int:game_id>', methods=['POST'])
@admin_required
def delete_game(game_id):
    game = Game.query.get_or_404(game_id)
    db.session.delete(game)
    db.session.commit()
    
    flash('Game deleted successfully!')
    return redirect(url_for('admin.dashboard'))

#default page for admins
#if authenticated, redirects to dashboard
#if not authenticated, redirects to login
@admin.route('/')
def admin_home():
    # If user is already authenticated and is admin, redirect to dashboard
    if current_user.is_authenticated and current_user.is_administrator:
        return redirect(url_for('admin.dashboard'))
    # If user is not authenticated or is not admin, redirect to login
    return redirect(url_for('admin.login'))

#page for accessing game logs
@admin.route('/logs')
@login_required
@admin_required
def game_logs():
    logs = Log.query.order_by(Log.timestamp.desc()).all()
    return render_template('gog/admin/game_logs.html', logs=logs)

#page for accessing the tournaments ranking
@admin.route('/ranking')
@login_required
@admin_required
def admin_gog_ranking():
    teams_a = Teams.query.filter_by(team_type=TeamType.A)\
        .join(GamePoints)\
        .with_entities(
            Teams,
            func.sum(GamePoints.final_points).label('total_points')
        )\
        .group_by(Teams.id)\
        .order_by(func.sum(GamePoints.final_points).asc()).all()

    teams_b = Teams.query.filter_by(team_type=TeamType.B)\
        .join(GamePoints)\
        .with_entities(
            Teams,
            func.sum(GamePoints.final_points).label('total_points')
        )\
        .group_by(Teams.id)\
        .order_by(func.sum(GamePoints.final_points).asc()).all()

    games = Game.query.all()
    game_leaderboards = {'A_Teams': [], 'B_Teams': []}
    
    for game in games:
        a_ranking = GamePoints.query.filter_by(game_id=game.id)\
            .join(Teams)\
            .filter(Teams.team_type == TeamType.A)\
            .order_by(
                GamePoints.points.asc() if game.scoring_preference == ScoringPreference.LOWER
                else GamePoints.points.desc()
            ).all()
            
        b_ranking = GamePoints.query.filter_by(game_id=game.id)\
            .join(Teams)\
            .filter(Teams.team_type == TeamType.B)\
            .order_by(
                GamePoints.points.asc() if game.scoring_preference == ScoringPreference.LOWER
                else GamePoints.points.desc()
            ).all()
            
        game_leaderboards['A_Teams'].append((game, a_ranking))
        game_leaderboards['B_Teams'].append((game, b_ranking))
    
    return render_template('gog/admin/gog_ranking.html',
                         teams_a=teams_a,
                         teams_b=teams_b,
                         games=games,
                         game_leaderboards=game_leaderboards)
