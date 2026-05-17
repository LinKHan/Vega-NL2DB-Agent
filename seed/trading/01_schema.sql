
CREATE TABLE "user" (
  user_id        BIGINT PRIMARY KEY,
  email          TEXT UNIQUE NOT NULL,
  country        CHAR(2) NOT NULL,
  registered_at  TIMESTAMP NOT NULL,
  kyc_level      SMALLINT NOT NULL,    -- 1: 邮箱 | 2: 身份证 | 3: 进阶 KYC（机构/高净值）
  status         TEXT NOT NULL          -- ACTIVE / SUSPENDED
);
CREATE TABLE "order" (
  order_id    BIGINT PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES "user"(user_id),
  symbol      TEXT NOT NULL,            -- 跨库逻辑外键 → market_data.symbol
  side        TEXT NOT NULL,            -- BUY / SELL
  type        TEXT NOT NULL,            -- LIMIT / MARKET
  price       NUMERIC,                  -- LIMIT 才有，MARKET 为 NULL
  quantity    NUMERIC NOT NULL,
  filled_qty  NUMERIC NOT NULL DEFAULT 0,
  status      TEXT NOT NULL,            -- NEW / PARTIALLY_FILLED / FILLED / CANCELLED
  created_at  TIMESTAMP NOT NULL
);
CREATE INDEX ON "order"(user_id);
CREATE INDEX ON "order"(symbol);
CREATE INDEX ON "order"(status);
CREATE INDEX ON "order"(created_at);
CREATE TABLE trade (
  trade_id    BIGINT PRIMARY KEY,
  order_id    BIGINT NOT NULL REFERENCES "order"(order_id),
  user_id     BIGINT NOT NULL,          -- 冗余字段，便于聚合
  symbol      TEXT NOT NULL,
  side        TEXT NOT NULL,
  price       NUMERIC NOT NULL,         -- 成交价
  quantity    NUMERIC NOT NULL,
  fee         NUMERIC NOT NULL,         -- 手续费
  fee_asset   TEXT NOT NULL,            -- 手续费币种（一般 USDT）
  traded_at   TIMESTAMP NOT NULL
);
CREATE INDEX ON trade(user_id);
CREATE INDEX ON trade(symbol);
CREATE INDEX ON trade(traded_at);
