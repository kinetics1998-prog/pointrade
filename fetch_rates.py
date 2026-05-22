#!/usr/bin/env python3
"""
fetch_rates.py — тікер курсів валют для pointrade.business/news
Тиждень 1 з customs_section_plan.

Джерела:
- НБУ офіційний (безкоштовний JSON)
- Privat24 готівка (безкоштовний JSON)

Запуск:
    python3 fetch_rates.py        # збирає → пише data/rates.json

GitHub Actions cron: щогодини (08:00-20:00 Europe/Kyiv)

Вихідний формат data/rates.json:
{
  "updated": "2026-05-22T14:30:00",
  "official": {
    "USD": 41.25, "EUR": 44.80, "PLN": 10.45, "TRY": 1.05, "RON": 9.10
  },
  "cash": {
    "USD": {"buy": 41.15, "sell": 41.45},
    "EUR": {"buy": 44.65, "sell": 45.00}
  }
}
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUT_FILE = DATA_DIR / "rates.json"

NBU_URL = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
PRIVAT_URL = "https://api.privatbank.ua/p24api/pubinfo?exchange&json&coursid=11"

TRACKED_CURRENCIES = ("USD", "EUR", "PLN", "TRY", "RON", "GBP")


def fetch_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Pointrade/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_nbu() -> dict:
    """Офіційний курс НБУ — оновлюється щодня ~12:00."""
    try:
        data = fetch_json(NBU_URL)
        return {
            item["cc"]: round(float(item["rate"]), 4)
            for item in data
            if item.get("cc") in TRACKED_CURRENCIES
        }
    except Exception as e:
        print(f"⚠ NBU error: {e}")
        return {}


def fetch_privat() -> dict:
    """Готівковий курс Приватбанку — оновлюється часто."""
    try:
        data = fetch_json(PRIVAT_URL)
        out = {}
        for item in data:
            ccy = item.get("ccy")
            if ccy in TRACKED_CURRENCIES:
                out[ccy] = {
                    "buy": round(float(item["buy"]), 2),
                    "sell": round(float(item["sale"]), 2),
                }
        return out
    except Exception as e:
        print(f"⚠ Privat error: {e}")
        return {}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    official = fetch_nbu()
    cash = fetch_privat()

    result = {
        "updated": datetime.now().isoformat(timespec="seconds"),
        "official": official,
        "cash": cash,
    }

    OUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✅ {OUT_FILE}")
    print(f"   NBU: {len(official)} валют   Privat: {len(cash)} валют")
    if official:
        print(f"   USD: {official.get('USD', '—')}   EUR: {official.get('EUR', '—')}   PLN: {official.get('PLN', '—')}   TRY: {official.get('TRY', '—')}")


if __name__ == "__main__":
    main()
