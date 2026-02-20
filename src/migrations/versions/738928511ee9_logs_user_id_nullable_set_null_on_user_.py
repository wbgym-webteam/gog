"""logs user_id nullable SET NULL on user delete

Revision ID: 738928511ee9
Revises: 6a1f068be7c5
Create Date: 2026-02-20 18:35:20.561568

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '738928511ee9'
down_revision = '6a1f068be7c5'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite doesn't support ALTER COLUMN or named FK constraints, so batch_alter
    # rebuilds the table. We just declare the final desired schema — no drop_constraint needed.
    with op.batch_alter_table('logs', schema=None, recreate='always') as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade():
    with op.batch_alter_table('logs', schema=None, recreate='always') as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
