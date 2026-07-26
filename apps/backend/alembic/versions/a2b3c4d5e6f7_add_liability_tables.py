"""add liability tables

Revision ID: a2b3c4d5e6f7
Revises: 9b1c2d3e4f5a
Create Date: 2026-07-26 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "9b1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


payment_cycle_enum = sa.Enum(
    "WEEKLY", "BIWEEKLY", "MONTHLY", "QUARTERLY", name="paymentcycle"
)


def upgrade() -> None:
    """升級資料庫結構。"""
    op.create_table(
        "liabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False, comment="對應持倉的標的代號"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="負債名稱，如「房貸」「車貸」"),
        sa.Column(
            "principal",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            comment="原始本金總額",
        ),
        sa.Column("payment_cycle", payment_cycle_enum, nullable=False),
        sa.Column("total_periods", sa.Integer(), nullable=False, comment="總期數"),
        sa.Column(
            "payment_amount",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            comment="每期還款金額",
        ),
        sa.Column(
            "payment_day",
            sa.Integer(),
            nullable=True,
            comment="每期繳款日（1-31，週期為月/季時適用）",
        ),
        sa.Column("start_date", sa.Date(), nullable=True, comment="起始日"),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否進行中（結清後為 False）"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_liabilities_user_id"),
        "liabilities",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "liability_payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("liability_id", sa.String(length=36), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False, comment="還款日期"),
        sa.Column(
            "amount",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            comment="還款金額",
        ),
        sa.Column(
            "transaction_id",
            sa.String(length=36),
            nullable=True,
            comment="關聯的沖減交易",
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["liability_id"], ["liabilities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_liability_payments_liability_id"),
        "liability_payments",
        ["liability_id"],
        unique=False,
    )


def downgrade() -> None:
    """降級資料庫結構。"""
    op.drop_index(
        op.f("ix_liability_payments_liability_id"), table_name="liability_payments"
    )
    op.drop_table("liability_payments")
    op.drop_index(op.f("ix_liabilities_user_id"), table_name="liabilities")
    op.drop_table("liabilities")
    payment_cycle_enum.drop(op.get_bind(), checkfirst=True)
