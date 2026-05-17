
CREATE TABLE symbol (
  symbol      TEXT PRIMARY KEY,
  base_asset  TEXT NOT NULL,
  quote_asset TEXT NOT NULL,
  status      TEXT NOT NULL
);
CREATE TABLE kline_1d (
  symbol       TEXT NOT NULL REFERENCES symbol(symbol),
  open_time    DATE NOT NULL,
  open         NUMERIC NOT NULL,
  high         NUMERIC NOT NULL,
  low          NUMERIC NOT NULL,
  close        NUMERIC NOT NULL,
  volume       NUMERIC NOT NULL,        -- 基础币成交量
  quote_volume NUMERIC NOT NULL,        -- 计价币成交额
  num_trades   INTEGER NOT NULL,
  PRIMARY KEY (symbol, open_time)
);
CREATE INDEX ON kline_1d(open_time);
