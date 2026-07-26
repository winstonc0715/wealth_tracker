"""add indexes for common query shapes

常用查詢缺索引：
- transactions (portfolio_id, symbol)：重算持倉、持倉調整
- transactions (portfolio_id, executed_at)：交易分頁排序、歷史回溯
- portfolios (user_id)：列出用戶組合、歸屬檢查
- dca_schedules (portfolio_id)、liabilities (portfolio_id)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-26
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_transactions_portfolio_symbol",
        "transactions",
        ["portfolio_id", "symbol"],
    )
    op.create_index(
        "ix_transactions_portfolio_executed",
        "transactions",
        ["portfolio_id", "executed_at"],
    )
    op.create_index(
        "ix_portfolios_user_id",
        "portfolios",
        ["user_id"],
    )
    op.create_index(
        "ix_dca_schedules_portfolio_id",
        "dca_schedules",
        ["portfolio_id"],
    )
    op.create_index(
        "ix_liabilities_portfolio_id",
        "liabilities",
        ["portfolio_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_liabilities_portfolio_id", table_name="liabilities")
    op.drop_index("ix_dca_schedules_portfolio_id", table_name="dca_schedules")
    op.drop_index("ix_portfolios_user_id", table_name="portfolios")
    op.drop_index("ix_transactions_portfolio_executed", table_name="transactions")
    op.drop_index("ix_transactions_portfolio_symbol", table_name="transactions")
