"""add account activity

Revision ID: 97404229e75e
Revises: bfc0a39bfe02
Create Date: 2021-09-07 10:38:41.655301

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '97404229e75e'
down_revision = 'bfc0a39bfe02'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_activity',
    sa.Column('puppet_id', sa.BigInteger(), nullable=False),
    sa.Column('first_activity_ts', sa.Integer(), nullable=False),
    sa.Column('last_activity_ts', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('puppet_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_activity')
    # ### end Alembic commands ###
