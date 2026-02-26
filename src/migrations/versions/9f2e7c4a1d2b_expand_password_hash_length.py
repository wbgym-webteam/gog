"""expand password hash length

Revision ID: 9f2e7c4a1d2b
Revises: 1b7c2f0d9c1a
Create Date: 2026-02-26 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f2e7c4a1d2b'
down_revision = '1b7c2f0d9c1a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None, recreate='always') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=128),
            type_=sa.String(length=255),
            existing_nullable=False
        )

    with op.batch_alter_table('admins', schema=None, recreate='always') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=128),
            type_=sa.String(length=255),
            existing_nullable=False
        )


def downgrade():
    with op.batch_alter_table('admins', schema=None, recreate='always') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=255),
            type_=sa.String(length=128),
            existing_nullable=False
        )

    with op.batch_alter_table('users', schema=None, recreate='always') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=255),
            type_=sa.String(length=128),
            existing_nullable=False
        )
