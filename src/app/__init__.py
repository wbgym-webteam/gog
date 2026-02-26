import os
import sqlite3
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, with_loader_criteria


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def _load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _build_database_uri() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    backend = os.environ.get("DB_BACKEND", "sqlite").strip().lower()
    if backend in {"postgres", "postgresql", "psql"}:
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5432")
        name = os.environ.get("DB_NAME", "gog")
        user = quote_plus(os.environ.get("DB_USER", "postgres"))
        password = quote_plus(os.environ.get("DB_PASSWORD", ""))
        auth = user if not password else f"{user}:{password}"
        return f"postgresql://{auth}@{host}:{port}/{name}"

    db_path_value = os.environ.get("SQLITE_DB_PATH", "src/wbgym.db").strip()
    if db_path_value == ":memory:":
        return "sqlite:///:memory:"

    db_path = Path(db_path_value)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    db_path = db_path.resolve()
    return f"sqlite:///{db_path.as_posix()}"


_load_env_file(ENV_FILE)

# Enable FK enforcement for every SQLite connection
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(Session, "do_orm_execute")
def _filter_soft_deleted(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("include_deleted", False):
        return

    from .models import SoftDeleteMixin
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )

class Config:
    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static")
    app.config.from_object(config_class)

    # Update session configuration
    app.config["SESSION_COOKIE_NAME"] = "admin_session"
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
    app.config["SESSION_PROTECTION"] = "strong"

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    socketio.init_app(app, cors_allowed_origins="*")

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User, Admin
        # Flask-Login stores only one ID; check the session to know which table to query
        from flask import session
        if session.get("is_admin"):
            return Admin.query.get(int(user_id))
        return User.query.get(int(user_id))

    with app.app_context():
        from . import models
        db.create_all()

        from .gog_views import gog
        from .views import main_views
        from .auth import auth
        from .admin_views import admin

        app.register_blueprint(gog, url_prefix="/gog")
        app.register_blueprint(main_views, url_prefix="/")
        app.register_blueprint(auth, url_prefix="/auth")
        app.register_blueprint(admin)

    # Register CLI commands
    from . import cli
    cli.init_app(app)

    # Register socket events
    from . import sockets

    return app
