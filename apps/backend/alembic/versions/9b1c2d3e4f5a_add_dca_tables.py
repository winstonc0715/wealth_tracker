"""add dca tables

Revision ID: 9b1c2d3e4f5a
Revises: 6fee44d3d0de
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b1c2d3e4f5a"
down_revision: Union[str, Sequence[str], None] = "6fee44d3d0de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


investment_type_enum = sa.Enum("AMOUNT", "SHARES", name="investmenttype")
execution_status_enum = sa.Enum(
    "PENDING", "CONFIRMED", "SKIPPED", "FAILED", name="executionstatus"
)


def upgrade() -> None:
    """升級資料庫結構。"""
    op.create_table(
        "dca_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False, comment="標的代碼"),
        sa.Column("asset_name", sa.String(length=100), nullable=True, comment="標的名稱"),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("broker", sa.String(length=20), nullable=False, comment="券商識別"),
        sa.Column("investment_type", investment_type_enum, nullable=False),
        sa.Column(
            "target_amount",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="目標金額（定額模式）",
        ),
        sa.Column(
            "target_shares",
            sa.Numeric(precision=18, scale=8),
            nullable=True,
            comment="目標股數（定股模式）",
        ),
        sa.Column(
            "execution_days",
            sa.String(length=100),
            nullable=False,
            comment="扣款日 JSON，如 [3,16]",
        ),
        sa.Column(
            "fee_discount",
            sa.Numeric(precision=5, scale=4),
            nullable=False,
            comment="手續費折扣",
        ),
        sa.Column("auto_confirm", sa.Boolean(), nullable=False, comment="是否自動確認"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否啟用"),
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
        sa.ForeignKeyConstraint(["category_id"], ["asset_categories.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dca_schedules_user_id"),
        "dca_schedules",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "dca_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("schedule_id", sa.String(length=36), nullable=False),
        sa.Column("execution_date", sa.Date(), nullable=False, comment="執行日期"),
        sa.Column("status", execution_status_enum, nullable=False),
        sa.Column(
            "estimated_price",
            sa.Numeric(precision=18, scale=8),
            nullable=True,
            comment="系統估算價格（收盤價）",
        ),
        sa.Column(
            "actual_price",
            sa.Numeric(precision=18, scale=8),
            nullable=True,
            comment="用戶確認的實際成交價",
        ),
        sa.Column(
            "quantity",
            sa.Numeric(precision=18, scale=8),
            nullable=True,
            comment="計算出的股數",
        ),
        sa.Column(
            "fee",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="手續費",
        ),
        sa.Column(
            "total_cost",
            sa.Numeric(precision=18, scale=4),
            nullable=True,
            comment="總扣款金額",
        ),
        sa.Column(
            "transaction_id",
            sa.String(length=36),
            nullable=True,
            comment="關聯的交易紀錄",
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["schedule_id"], ["dca_schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "schedule_id", "execution_date", name="uq_schedule_execution_date"
        ),
    )
    op.create_index(
        op.f("ix_dca_executions_schedule_id"),
        "dca_executions",
        ["schedule_id"],
        unique=False,
    )


def downgrade() -> None:
    """降級資料庫結構。"""
    op.drop_index(op.f("ix_dca_executions_schedule_id"), table_name="dca_executions")
    op.drop_table("dca_executions")
    op.drop_index(op.f("ix_dca_schedules_user_id"), table_name="dca_schedules")
    op.drop_table("dca_schedules")
    execution_status_enum.drop(op.get_bind(), checkfirst=True)
    investment_type_enum.drop(op.get_bind(), checkfirst=True)
