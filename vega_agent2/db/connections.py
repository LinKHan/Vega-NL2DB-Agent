"""PostgreSQL connection and time-anchor helpers.

Responsibilities:
- Expose the three database URIs from ``config``.
- Provide small scalar query helpers used during startup.
- Compute the business time anchor from market data, not synthetic trade tails.

Used by:
- ``db.runner`` for query execution.
- ``core.planner`` and ``render.audit`` for the latest data date.
"""

import psycopg2

from vega_agent2.config import DB_URIS


def get_db_scalar(db: str, sql: str, fallback=None):
    try:
        conn = psycopg2.connect(DB_URIS[db])
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute(sql)
        value = cur.fetchone()[0]
        cur.close()
        conn.close()
        return value
    except Exception:
        return fallback


DB_LATEST_DATES = {
    "market_data": get_db_scalar("market_data", "SELECT MAX(open_time) FROM kline_1d", "2024-12-31"),
    "trading_orders": get_db_scalar("trading", 'SELECT MAX(created_at) FROM "order"', "2024-12-31"),
    "trading_trades": get_db_scalar("trading", "SELECT MAX(traded_at) FROM trade", "2024-12-31"),
    "accounts": get_db_scalar("accounts", "SELECT MAX(updated_at) FROM account", "2024-12-31"),
}

# Business-relative words ("today", "this year") follow the market dataset.
DB_LATEST_DATE = str(DB_LATEST_DATES.get("market_data") or "2024-12-31")[:10]

