
CREATE TABLE account (
  account_id  BIGINT PRIMARY KEY,
  user_id     BIGINT NOT NULL,          -- 跨库逻辑外键 → trading.user
  asset       TEXT NOT NULL,            -- BTC / ETH / SOL / BNB / XRP / USDT
  balance     NUMERIC NOT NULL,
  locked      NUMERIC NOT NULL DEFAULT 0,
  updated_at  TIMESTAMP NOT NULL,
  UNIQUE (user_id, asset)
);
CREATE INDEX ON account(user_id);
CREATE INDEX ON account(asset);
CREATE TABLE ledger (
  ledger_id   BIGINT PRIMARY KEY,
  user_id     BIGINT NOT NULL,
  asset       TEXT NOT NULL,
  amount      NUMERIC NOT NULL,         -- 正负，+ 入账 / - 出账
  type        TEXT NOT NULL,            -- DEPOSIT / WITHDRAW / TRADE_BUY / TRADE_SELL / FEE
  ref_id      BIGINT,                   -- trade_id 或外部 txid
  created_at  TIMESTAMP NOT NULL
);
CREATE INDEX ON ledger(user_id);
CREATE INDEX ON ledger(type);
CREATE INDEX ON ledger(created_at);
