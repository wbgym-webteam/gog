import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from datetime import timedelta

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///wbgym.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static')
    app.config.from_object(config_class)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wbgym.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'your-secret-key-here'

    # Update session configuration
    app.config['SESSION_COOKIE_NAME'] = 'admin_session'
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    app.config['SESSION_PROTECTION'] = 'strong'

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    socketio.init_app(app, cors_allowed_origins="*")

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    with app.app_context():
        from . import models
        db.create_all()

        from .gog_views import gog
        from .views import main_views
        from .auth import auth
        from .admin_views import admin

        app.register_blueprint(gog, url_prefix='/gog')
        app.register_blueprint(main_views, url_prefix='/')
        app.register_blueprint(auth, url_prefix='/auth')
        app.register_blueprint(admin)

    # Register CLI commands
    from . import cli
    cli.init_app(app)

    # Register socket events
    from . import sockets

    return app
