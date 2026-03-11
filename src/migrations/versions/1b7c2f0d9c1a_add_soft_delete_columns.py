"""add soft delete columns

Revision ID: 1b7c2f0d9c1a
Revises: 738928511ee9
Create Date: 2026-02-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b7c2f0d9c1a'
down_revision = '738928511ee9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'], unique=False)

    op.add_column('admins', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_admins_deleted_at', 'admins', ['deleted_at'], unique=False)

    op.add_column('teams', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_teams_deleted_at', 'teams', ['deleted_at'], unique=False)

    op.add_column('games', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_games_deleted_at', 'games', ['deleted_at'], unique=False)

    op.add_column('game_points', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_game_points_deleted_at', 'game_points', ['deleted_at'], unique=False)

    op.add_column('logs', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_logs_deleted_at', 'logs', ['deleted_at'], unique=False)

    op.add_column('conversations', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_conversations_deleted_at', 'conversations', ['deleted_at'], unique=False)

    op.add_column('messages', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_messages_deleted_at', 'messages', ['deleted_at'], unique=False)


def downgrade():
    op.drop_index('ix_messages_deleted_at', table_name='messages')
    with op.batch_alter_table('messages', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')

    op.drop_index('ix_conversations_deleted_at', table_name='conversations')
    with op.batch_alter_table('conversations', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')

    op.drop_index('ix_logs_deleted_at', table_name='logs')
    with op.batch_alter_table('logs', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')

    op.drop_index('ix_game_points_deleted_at', table_name='game_points')
    with op.batch_alter_table('game_points', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')

    op.drop_index('ix_games_deleted_at', table_name='games')
    with op.batch_alter_table('games', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')

    op.drop_index('ix_teams_deleted_at', table_name='teams')
    with op.batch_alter_table('teams', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')

    op.drop_index('ix_admins_deleted_at', table_name='admins')
    with op.batch_alter_table('admins', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')

    op.drop_index('ix_users_deleted_at', table_name='users')
    with op.batch_alter_table('users', schema=None, recreate='always') as batch_op:
        batch_op.drop_column('deleted_at')
