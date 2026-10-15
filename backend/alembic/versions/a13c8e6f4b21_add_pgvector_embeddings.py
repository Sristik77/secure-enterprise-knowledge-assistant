"""Change document chunk embeddings from JSONB to pgvector."""

from typing import Sequence, Union

from alembic import op

revision: str = "a13c8e6f4b21"
down_revision: Union[str, None] = "256fb3c7f951"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgvector and convert existing embeddings without dropping chunks."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE vector(384)
        USING CASE
            WHEN embedding IS NULL THEN NULL
            ELSE embedding::text::vector(384)
        END
        """
    )


def downgrade() -> None:
    """Restore JSONB embeddings."""
    op.execute(
        """
        ALTER TABLE document_chunks
        ALTER COLUMN embedding TYPE jsonb
        USING CASE
            WHEN embedding IS NULL THEN NULL
            ELSE embedding::text::jsonb
        END
        """
    )
