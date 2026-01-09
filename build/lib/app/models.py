from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from . import db  # Only import db from __init__.py

class User(UserMixin, db.Model):    #creates the regular users Accound
    __tablename__ = 'users'  # Add explicit table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(50))

    __mapper_args__ = {
        'polymorphic_identity': 'user',
        'polymorphic_on': type
    }

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_administrator(self):
        return self.is_admin

    @classmethod
    def create_admin(cls, username, password):
        user = cls(username=username, is_admin=True)
        user.set_password(password)
        return user

    logs = db.relationship('Log', 
                          back_populates='user',
                          cascade='all, delete-orphan',
                          passive_deletes=True)

class Admin(User):  #creates the admin/super users Account
    __mapper_args__ = {
        'polymorphic_identity': 'admin',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_admin = True

class TeamType(Enum):   #seperates teams into A and B
    A = 'A'
    B = 'B'


class DependencyType(Enum): #creates the dependency type for the games
    NONE = 'none'
    POINT_DEPENDENT = 'point'
    TIME_DEPENDENT = 'time'

    def get_german_text(self):
        translations = {
            'none': 'Keine',
            'point': 'Punkteabhängig',
            'time': 'Zeitabhängig'
        }
        return translations[self.value]


class ScoringPreference(Enum):  
    HIGHER = 'HIGHER'
    LOWER = 'LOWER'
    # Add temporary backwards compatibility
    higher = 'HIGHER'
    lower = 'LOWER'

    def get_german_text(self):
        translations = {
            'HIGHER': 'Höhere Punktzahl ist besser',
            'LOWER': 'Niedrigere Punktzahl ist besser'
        }
        return translations[self.value]


class Teams(db.Model):  #creates the model for the teams
    __tablename__ = 'teams'
    id = db.Column(db.String(10), primary_key=True)  # Unique ID like a1, a2, b1, b2
    team_name = db.Column(db.String(100), nullable=True)  
    points = db.Column(db.Integer, default=0)
    team_type = db.Column(db.Enum(TeamType), nullable=False)  # Choice constraint
    
    game_points = db.relationship('GamePoints', #creates the relationship between the teams and the game points
                                back_populates='team',
                                cascade='all, delete-orphan',
                                passive_deletes=True)
    
    logs = db.relationship('Log',   #creates the relationship between the teams and the logs
                          back_populates='team',
                          cascade='all, delete-orphan',
                          passive_deletes=True)

    def __init__(self, team_type, team_number):
        self.id = f"{team_type.lower()}{team_number}"
        self.team_name = self.id  # Default name is the same as ID
        self.team_type = TeamType(team_type)

    def __repr__(self):
        return f"{self.team_name} ({self.team_type.value})"

class Game(db.Model):   #creates the model for the games
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    dependency_type = db.Column(db.String(10), nullable=False)  # 'time' or 'point'
    scoring_preference = db.Column(db.Enum(ScoringPreference), nullable=False)  # Change to use Enum
    logs = db.relationship('Log', back_populates='game', lazy=True)

    def get_german_dependency_type(self):
        return DependencyType(self.dependency_type).get_german_text()
    
    def get_german_scoring_preference(self):
        return self.scoring_preference.get_german_text()  # Access enum value directly

    def __repr__(self):
        return f"{self.name} ({self.get_german_dependency_type()}, {self.get_german_scoring_preference()})"


class GamePoints(db.Model): #defines the model for the game points
    __tablename__ = 'game_points'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(10), 
                       db.ForeignKey('teams.id', ondelete='CASCADE'),
                       nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    points = db.Column(db.Integer, default=0)  # for point dependent games
    time_taken = db.Column(db.Time, nullable=True)  # Used for time-based games
    final_points = db.Column(db.Integer, default=0)  # Rank-based points
    
    # Updated relationship with back_populates
    team = db.relationship('Teams', back_populates='game_points')
    game = db.relationship('Game', backref=db.backref('gamepoints', lazy=True))

    def __repr__(self):
        return f"{self.team.team_name} - {self.game.name}: {self.points} points"


class Log(db.Model):    #creates the model for the logs and determines what comes into a Log
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(10),
                       db.ForeignKey('teams.id', ondelete='CASCADE'),
                       nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    points = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer,
                       db.ForeignKey('users.id', ondelete='CASCADE'),
                       nullable=False)

    # Update these relationship definitions
    team = db.relationship('Teams', back_populates='logs')
    user = db.relationship('User', back_populates='logs')
    game = db.relationship('Game', back_populates='logs')


class Conversation(db.Model):
    """One conversation per user with the admin team"""
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('conversation', uselist=False))
    messages = db.relationship('Message', back_populates='conversation', cascade='all, delete-orphan', order_by='Message.created_at')


class Message(db.Model):
    """Individual message within a conversation"""
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_from_admin = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversation = db.relationship('Conversation', back_populates='messages')
    sender = db.relationship('User')