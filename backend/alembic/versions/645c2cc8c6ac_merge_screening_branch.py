"""merge_screening_branch

Revision ID: 645c2cc8c6ac
Revises: h80008screening, k110011platformadmin
Create Date: 2026-05-08 17:19:08.672065
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '645c2cc8c6ac'
down_revision: Union[str, None] = ('h80008screening', 'k110011platformadmin')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
