#gog\src\app\admin_views.py
from flask import Blueprint, session, request, redirect, url_for, flash, render_template
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from functools import wraps
from .models import User, Teams, TeamType, Game, DependencyType, ScoringPreference, Admin, GamePoints, Log, db, Conversation, Message
from datetime import datetime
import logging
from sqlalchemy import func
from . import db, socketio

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

    # Debug: Check all messages and their is_read values
    all_messages = Message.query.all()
    logger.info(f"Total messages in DB: {len(all_messages)}")
    for msg in all_messages[-5:]:  # Show last 5 messages
        logger.info(f"  Message {msg.id}: is_from_admin={msg.is_from_admin} (type: {type(msg.is_from_admin)}), is_read={msg.is_read} (type: {type(msg.is_read)})")

    # Count unread messages from users
    unread_count = Message.query.filter(
        Message.is_from_admin == False,
        Message.is_read == False
    ).count()
    logger.info(f"Dashboard loading: unread_count = {unread_count}")

    return render_template('gog/admin/dashboard.html', users=users, teams=teams, games=games, admins=admins, unread_count=unread_count)

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

#page for editing a game log
@admin.route('/logs/edit/<int:log_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_log(log_id):
    log = Log.query.get_or_404(log_id)

    if request.method == 'POST':
        team_id = request.form.get('team_id')
        game_id = request.form.get('game_id')
        points = request.form.get('points')

        try:
            points = int(points)
            game_id = int(game_id)

            # Update the log entry
            log.team_id = team_id
            log.game_id = game_id
            log.points = points

            # Update or create the corresponding GamePoints entry
            game_point = GamePoints.query.filter_by(
                team_id=team_id,
                game_id=game_id
            ).first()

            if game_point:
                game_point.points = points
            else:
                game_point = GamePoints(team_id=team_id, game_id=game_id, points=points)
                db.session.add(game_point)

            db.session.commit()

            # Recalculate rankings for the affected game
            from .gog_views import calculate_ranked_points
            calculate_ranked_points(game_id)

            flash('Log erfolgreich aktualisiert!')
            return redirect(url_for('admin.game_logs'))

        except ValueError:
            flash('Ungültiges Punkteformat!')
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Aktualisieren des Logs: {str(e)}')

    teams = Teams.query.all()
    games = Game.query.all()
    return render_template('gog/admin/edit_log.html', log=log, teams=teams, games=games)

#function for deleting a game log
@admin.route('/logs/delete/<int:log_id>', methods=['POST'])
@login_required
@admin_required
def delete_log(log_id):
    log = Log.query.get_or_404(log_id)
    game_id = log.game_id
    team_id = log.team_id

    try:
        db.session.delete(log)

        # Check if there are other logs for this team/game combination
        remaining_logs = Log.query.filter_by(team_id=team_id, game_id=game_id).count()

        # If no more logs exist, delete the GamePoints entry as well
        if remaining_logs == 0:
            game_point = GamePoints.query.filter_by(team_id=team_id, game_id=game_id).first()
            if game_point:
                db.session.delete(game_point)

        db.session.commit()

        # Recalculate rankings for the affected game
        from .gog_views import calculate_ranked_points
        calculate_ranked_points(game_id)

        flash('Log erfolgreich gelöscht!')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen des Logs: {str(e)}')

    return redirect(url_for('admin.game_logs'))

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


def get_unread_message_count():
    """Get total count of unread messages from users (not from admins)"""
    return Message.query.filter_by(is_from_admin=False, is_read=False).count()


@admin.route('/messages')
@login_required
@admin_required
def messages_inbox():
    """View all conversations with users"""
    conversations = Conversation.query.order_by(Conversation.updated_at.desc()).all()

    for conv in conversations:
        conv.unread_count = Message.query.filter(
            Message.conversation_id == conv.id,
            Message.is_from_admin == False,  # Messages FROM users
            Message.is_read == False         # That are NOT read
        ).count()

    # Recalculate global unread count exactly as in dashboard
    unread_count = Message.query.filter(
        Message.is_from_admin == False,
        Message.is_read == False
    ).count()
    
    return render_template('gog/admin/messages_inbox.html',
                           conversations=conversations,
                           unread_count=unread_count)


@admin.route('/messages/<int:conversation_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def messages_conversation(conversation_id):
    """View and reply to a specific conversation"""
    conversation = Conversation.query.get_or_404(conversation_id)

    if request.method == 'POST':
        content = request.form.get('message', '').strip()
        if content:
            message = Message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                content=content,
                is_from_admin=True,
                is_read=False
            )
            db.session.add(message)
            conversation.updated_at = datetime.utcnow()
            db.session.commit()
            try:
                socketio.emit('notification', {
                    'type': 'new_message',
                    'conversation_id': conversation.id,
                    'from': current_user.username
                }, room=f'user_{conversation.user_id}')
            except Exception as e:
                logger.error(f"Socket emit failed: {e}")
            flash('Antwort gesendet!')
        return redirect(url_for('admin.messages_conversation', conversation_id=conversation_id))

    # Don't automatically mark messages as read - let admin do it manually
    unread_count = get_unread_message_count()
    return render_template('gog/admin/messages_conversation.html',
                         conversation=conversation,
                         unread_count=unread_count)


@admin.route('/messages/new', methods=['GET', 'POST'])
@login_required
@admin_required
def messages_new():
    """Start a new conversation with a user"""
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        content = request.form.get('message', '').strip()

        if not user_id:
            flash('Bitte einen Nutzer auswählen.')
            return redirect(url_for('admin.messages_new'))

        user = User.query.filter_by(id=user_id, is_admin=False).first()
        if not user:
            flash('Nutzer nicht gefunden.')
            return redirect(url_for('admin.messages_new'))

        # Get or create conversation for this user
        conversation = Conversation.query.filter_by(user_id=user.id).first()
        if not conversation:
            conversation = Conversation(user_id=user.id)
            db.session.add(conversation)
            db.session.commit()

        # Send message if provided
        if content:
            message = Message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                content=content,
                is_from_admin=True,
                is_read=False
            )
            db.session.add(message)
            conversation.updated_at = datetime.utcnow()
            db.session.commit()
            try:
                socketio.emit('notification', {
                    'type': 'new_message',
                    'conversation_id': conversation.id,
                    'from': current_user.username
                }, room=f'user_{conversation.user_id}')
            except Exception as e:
                logger.error(f"Socket emit failed: {e}")
                
            flash('Nachricht gesendet!')

        return redirect(url_for('admin.messages_conversation', conversation_id=conversation.id))

    # GET: Show user selection form
    # Get users without existing conversations
    users_with_conversations = db.session.query(Conversation.user_id).all()
    users_with_conv_ids = [u[0] for u in users_with_conversations]

    all_users = User.query.filter_by(is_admin=False).all()
    users_without_conv = [u for u in all_users if u.id not in users_with_conv_ids]
    users_with_conv = [u for u in all_users if u.id in users_with_conv_ids]

    unread_count = get_unread_message_count()
    return render_template('gog/admin/messages_new.html',
                         users_without_conv=users_without_conv,
                         users_with_conv=users_with_conv,
                         unread_count=unread_count)


@admin.route('/messages/<int:conversation_id>/mark-read', methods=['POST'])
@login_required
@admin_required
def mark_conversation_read(conversation_id):
    """Mark all user messages as read in a specific conversation"""
    unread_messages = Message.query.filter_by(
        conversation_id=conversation_id,
        is_from_admin=False,
        is_read=False
    ).all()

    for msg in unread_messages:
        msg.is_read = True
    db.session.commit()

    return '', 204
