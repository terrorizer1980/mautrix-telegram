"""Add more puppet info for rich profiles

Revision ID: 1bd9ab7c9e21
Revises: 9e9c89b0b877
Create Date: 2019-06-30 17:34:56.417236

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1bd9ab7c9e21"
down_revision = "9e9c89b0b877"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("puppet_portal",
                    sa.Column("puppet_id", sa.Integer(), nullable=False),
                    sa.Column("portal_id", sa.Integer(), nullable=False),
                    sa.Column("displayname", sa.String(), nullable=True),
                    sa.ForeignKeyConstraint(("portal_id",), ("portal.tgid",), ),
                    sa.ForeignKeyConstraint(("puppet_id",), ("puppet.id",), ),
                    sa.PrimaryKeyConstraint("puppet_id", "portal_id"))
    op.add_column("puppet", sa.Column("first_name", sa.String(), nullable=True))
    op.add_column("puppet", sa.Column("last_name", sa.String(), nullable=True))
    op.add_column("puppet", sa.Column("avatar_url", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("puppet") as batch_op:
        batch_op.drop_column("last_name")
        batch_op.drop_column("first_name")
        batch_op.drop_column("avatar_url")
    op.drop_table("puppet_portal")
