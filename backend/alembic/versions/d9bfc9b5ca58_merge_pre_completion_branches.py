"""merge_pre_completion_branches

Revision ID: d9bfc9b5ca58
Revises: 51a8d30455e1, m130013candidatesources
Create Date: 2026-05-12 01:40:11.329745
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'd9bfc9b5ca58'
down_revision: Union[str, None] = ('51a8d30455e1', 'm130013candidatesources')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
