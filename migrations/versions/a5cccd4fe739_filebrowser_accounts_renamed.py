"""filebrowser_accounts was renamed to sftpgo_accounts."""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a5cccd4fe739"
down_revision: str | Sequence[str] | None = "434c9eea09b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("filebrowser_accounts", "sftpgo_accounts")


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table("sftpgo_accounts", "filebrowser_accounts")
