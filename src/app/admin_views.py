#gog\src\app\admin_views.py
from flask import Blueprint, session, request, redirect, url_for, flash, render_template, send_file
from flask_login import login_required, current_user, login_user, logout_user
from functools import wraps
from .models import User, Admin, Teams, TeamType, Game, DependencyType, ScoringPreference, GamePoints, Log, db, Conversation, Message
from datetime import datetime
import io
import logging
from sqlalchemy import func
from . import db, socketio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__,
                  url_prefix='/gog/admin',
                  template_folder='templates/gog',
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
    if not request.endpoint:
        return

    if 'static' in request.endpoint or request.endpoint == 'admin.login':
        return

    if not current_user.is_authenticated or not session.get('is_admin'):
        session.clear()
        return redirect(url_for('admin.login'))

#defines the login page for the admin
@admin.route('/login', methods=['GET', 'POST'])
def login():
    if 'is_admin' in session and not current_user.is_authenticated:
        session.clear()

    if current_user.is_authenticated and session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Query the dedicated admins table
        admin_user = Admin.query.filter_by(username=username).first()

        if admin_user and admin_user.check_password(password):
            login_user(admin_user)
            session['is_admin'] = True
            session['user_id'] = admin_user.id
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
    if not current_user.is_authenticated or not session.get('is_admin'):
        return redirect(url_for('admin.login'))

    users = User.query.all()            # all regular users
    admins = Admin.query.all()          # all admins from the admins table
    teams = Teams.query.all()
    games = Game.query.all()

    all_messages = Message.query.all()
    logger.info(f"Total messages in DB: {len(all_messages)}")
    for msg in all_messages[-5:]:
        logger.info(f"  Message {msg.id}: is_from_admin={msg.is_from_admin} (type: {type(msg.is_from_admin)}), is_read={msg.is_read} (type: {type(msg.is_read)})")

    unread_count = Message.query.filter(
        Message.is_from_admin == False,
        Message.is_read == False
    ).count()
    logger.info(f"Dashboard loading: unread_count = {unread_count}")

    return render_template('gog/admin/dashboard.html', users=users, teams=teams, games=games, admins=admins, unread_count=unread_count)

#creates the form for creating a new regular user account
@admin.route('/users/create', methods=['GET'])
@admin_required
def create_user_form():
    return render_template('gog/admin/create_user.html')

@admin.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    username = request.form['username']
    password = request.form['password']

    if User.with_deleted().filter_by(username=username).first():
        flash('Username already exists!')
        return redirect(url_for('admin.dashboard'))

    # Also prevent collision with admin usernames
    if Admin.with_deleted().filter_by(username=username).first():
        flash('Username already exists!')
        return redirect(url_for('admin.dashboard'))

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash('User created successfully!')
    return redirect(url_for('admin.dashboard'))

#setup for deleting a regular user account
@admin.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    user.soft_delete()
    conversation = Conversation.query.filter_by(user_id=user.id).first()
    if conversation:
        conversation.soft_delete()
        for message in Message.query.filter_by(conversation_id=conversation.id).all():
            message.soft_delete()
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
    name = request.form['name']
    type_id = request.form['type']
    number = request.form['number']

    team_id = f"{type_id.lower()}{number}"

    if Teams.with_deleted().filter_by(id=team_id).first():
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
        team = Teams.query.get_or_404(team_id)
        logger.info(f"Found team to delete: {team.id}")

        points = GamePoints.query.filter_by(team_id=team_id).all()
        for point in points:
            point.soft_delete()
        logger.info(f"Soft-deleted {len(points)} game points records")

        logs = Log.query.filter_by(team_id=team_id).all()
        for log in logs:
            log.soft_delete()
        logger.info(f"Soft-deleted {len(logs)} log records")

        team.soft_delete()
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

    if not dependency_type in ['point', 'time']:
        flash('Invalid dependency type!', 'admin')
        return redirect(url_for('admin.create_game_form'))

    try:
        scoring_preference = ScoringPreference((scoring_pref or '').upper())
    except ValueError:
        flash('Invalid scoring preference!', 'admin')
        return redirect(url_for('admin.create_game_form'))

    game = Game(
        name=name,
        dependency_type=dependency_type,
        scoring_preference=scoring_preference
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
    for game_point in GamePoints.query.filter_by(game_id=game.id).all():
        game_point.soft_delete()
    for log in Log.query.filter_by(game_id=game.id).all():
        log.soft_delete()
    game.soft_delete()
    db.session.commit()

    flash('Game deleted successfully!')
    return redirect(url_for('admin.dashboard'))

#default page for admins
@admin.route('/')
def admin_home():
    if current_user.is_authenticated and current_user.is_administrator:
        return redirect(url_for('admin.dashboard'))
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

            log.team_id = team_id
            log.game_id = game_id
            log.points = points

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
        log.soft_delete()

        remaining_logs = Log.query.filter_by(team_id=team_id, game_id=game_id).count()

        if remaining_logs == 0:
            game_point = GamePoints.query.filter_by(team_id=team_id, game_id=game_id).first()
            if game_point:
                game_point.soft_delete()

        db.session.commit()

        from .gog_views import calculate_ranked_points
        calculate_ranked_points(game_id)

        flash('Log erfolgreich gelöscht!')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen des Logs: {str(e)}')

    return redirect(url_for('admin.game_logs'))

#page for accessing the tournament ranking
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
            Message.is_from_admin == False,
            Message.is_read == False
        ).count()

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
                admin_sender_id=current_user.id,  # link to admins table
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

        # Look up only in the users table (regular users)
        user = User.query.get(user_id)
        if not user:
            flash('Nutzer nicht gefunden.')
            return redirect(url_for('admin.messages_new'))

        conversation = Conversation.query.filter_by(user_id=user.id).first()
        if not conversation:
            conversation = Conversation.with_deleted().filter_by(user_id=user.id).first()
            if conversation and conversation.is_deleted:
                conversation.restore()
        if not conversation:
            conversation = Conversation(user_id=user.id)
            db.session.add(conversation)
            db.session.commit()

        if content:
            message = Message(
                conversation_id=conversation.id,
                admin_sender_id=current_user.id,  # link to admins table
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

    # GET: show user selection form — only regular users
    users_with_conversations = db.session.query(Conversation.user_id).all()
    users_with_conv_ids = [u[0] for u in users_with_conversations]

    all_users = User.query.all()
    users_without_conv = [u for u in all_users if u.id not in users_with_conv_ids]
    users_with_conv = [u for u in all_users if u.id in users_with_conv_ids]

    unread_count = get_unread_message_count()
    return render_template('gog/admin/messages_new.html',
                           users_without_conv=users_without_conv,
                           users_with_conv=users_with_conv,
                           unread_count=unread_count)


@admin.route('/certificates')
@login_required
@admin_required
def certificates():
    """Show top-3 from A teams and top-3 from B teams with certificate download buttons."""
    top3_a = _get_top3_by_type(TeamType.A)
    top3_b = _get_top3_by_type(TeamType.B)
    return render_template('gog/admin/certificates.html', top3_a=top3_a, top3_b=top3_b)


@admin.route('/certificates/download/<group>/<int:place>')
@login_required
@admin_required
def download_certificate(group, place):
    """Generate and return a certificate PNG for the given group (a/b) and place (1-3)."""
    if group not in ('a', 'b') or place not in (1, 2, 3):
        flash('Ungültige Anfrage.')
        return redirect(url_for('admin.certificates'))

    team_type = TeamType.A if group == 'a' else TeamType.B
    top3 = _get_top3_by_type(team_type)

    if place > len(top3):
        flash('Nicht genug Teams in der Rangliste.')
        return redirect(url_for('admin.certificates'))

    team, _ = top3[place - 1]
    from .certificate_generator import generate_certificate
    png_bytes = generate_certificate(
        team_name=team.team_name or team.id,
        year=datetime.utcnow().year,
        place=place,
    )
    filename = f'Urkunde_{group.upper()}-Teams_{place}_Platz_{(team.team_name or team.id).replace(" ", "_")}.png'
    return send_file(
        io.BytesIO(png_bytes),
        mimetype='image/png',
        as_attachment=True,
        download_name=filename,
    )


def _get_top3_by_type(team_type):
    """Return top-3 teams of a given TeamType, sorted by total final_points ascending (lower = better)."""
    results = (
        db.session.query(Teams, func.sum(GamePoints.final_points).label('total_points'))
        .join(GamePoints, GamePoints.team_id == Teams.id)
        .filter(Teams.team_type == team_type)
        .group_by(Teams.id)
        .order_by(func.sum(GamePoints.final_points).asc())
        .all()
    )
    return results[:3]


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
