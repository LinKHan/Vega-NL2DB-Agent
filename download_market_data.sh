#!/usr/bin/env bash
set -euo pipefail

mkdir -p raw/klines

SYMBOLS=(BTCUSDT ETHUSDT SOLUSDT BNBUSDT XRPUSDT)
MONTHS=(01 02 03 04 05 06 07 08 09 10 11 12)
YEAR=2024

for s in "${SYMBOLS[@]}"; do
  for m in "${MONTHS[@]}"; do
    fn="${s}-1d-${YEAR}-${m}"
    url="https://data.binance.vision/data/spot/monthly/klines/${s}/1d/${fn}.zip"
    [ -f "raw/klines/${fn}.csv" ] && continue
    curl -sLo "raw/klines/${fn}.zip" "$url"
    unzip -o -q "raw/klines/${fn}.zip" -d raw/klines/
    rm "raw/klines/${fn}.zip"
  done
done
echo "✅ Market data downloaded: $(ls raw/klines/*.csv | wc -l) files"
