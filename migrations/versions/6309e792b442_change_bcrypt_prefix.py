"""Change Bcrypt prefix."""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "6309e792b442"
down_revision: str | Sequence[str] | None = "a5cccd4fe739"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("update sftpgo_accounts set password = '$2a' || substr(password, 4)")
    op.execute("update thelounge_accounts set password = '$2a' || substr(password, 4)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("update sftpgo_accounts set password = '$2b' || substr(password, 4)")
    op.execute("update thelounge_accounts set password = '$2b' || substr(password, 4)")
