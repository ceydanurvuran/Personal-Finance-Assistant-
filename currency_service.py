import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests


CACHE_MINUTES = 10
REQUEST_TIMEOUT = (5, 15)
HEADERS = {"User-Agent": "FinanceAI/1.0"}

_cache = {"data": None, "time": None}
_lock = threading.Lock()


def _request_json(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def _fetch_tcmb_rates():
    response = requests.get(
        "https://www.tcmb.gov.tr/kurlar/today.xml",
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)

    rates = {}
    for currency in root.findall("Currency"):
        code = currency.attrib.get("CurrencyCode", "").upper()
        if code not in {"USD", "EUR", "GBP"}:
            continue

        value_text = (
            currency.findtext("ForexSelling")
            or currency.findtext("ForexBuying")
        )
        if value_text:
            rates[code.lower()] = 1 / float(value_text.replace(",", "."))

    if not all(code in rates for code in ("usd", "eur", "gbp")):
        raise ValueError("TCMB response did not contain all requested currencies")

    document_date = root.attrib.get("Date") or root.attrib.get("Tarih")
    return rates, "TCMB", document_date


def _fetch_frankfurter_rates():
    payload = _request_json(
        "https://api.frankfurter.app/latest?from=TRY&to=USD,EUR,GBP"
    )
    rates = payload.get("rates", {})
    if not all(code in rates for code in ("USD", "EUR", "GBP")):
        raise ValueError("Frankfurter response is incomplete")

    return {
        "usd": float(rates["USD"]),
        "eur": float(rates["EUR"]),
        "gbp": float(rates["GBP"])
    }, "Frankfurter", payload.get("date")


def _fetch_exchange_rate_api():
    payload = _request_json("https://open.er-api.com/v6/latest/TRY")
    rates = payload.get("rates", {})
    if not all(code in rates for code in ("USD", "EUR", "GBP")):
        raise ValueError("ExchangeRate API response is incomplete")

    return {
        "usd": float(rates["USD"]),
        "eur": float(rates["EUR"]),
        "gbp": float(rates["GBP"])
    }, "ExchangeRate-API", payload.get("time_last_update_utc")


def _fetch_crypto_rates(usd_try):
    try:
        payload = _request_json(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,ethereum&vs_currencies=try"
        )
        btc = float(payload.get("bitcoin", {}).get("try", 0))
        eth = float(payload.get("ethereum", {}).get("try", 0))
        if btc > 0 and eth > 0:
            return {"btc": btc, "eth": eth}, "CoinGecko"
    except Exception as exc:
        print("CoinGecko fetch error:", exc)

    try:
        btc_payload = _request_json(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCTRY"
        )
        eth_payload = _request_json(
            "https://api.binance.com/api/v3/ticker/price?symbol=ETHTRY"
        )
        btc = float(btc_payload.get("price", 0))
        eth = float(eth_payload.get("price", 0))
        if btc > 0 and eth > 0:
            return {"btc": btc, "eth": eth}, "Binance"
    except Exception as exc:
        print("Binance fetch error:", exc)

    try:
        btc_payload = _request_json(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot"
        )
        eth_payload = _request_json(
            "https://api.coinbase.com/v2/prices/ETH-USD/spot"
        )
        btc_usd = float(btc_payload.get("data", {}).get("amount", 0))
        eth_usd = float(eth_payload.get("data", {}).get("amount", 0))
        if btc_usd > 0 and eth_usd > 0 and usd_try > 0:
            return {
                "btc": btc_usd * usd_try,
                "eth": eth_usd * usd_try
            }, "Coinbase"
    except Exception as exc:
        print("Coinbase fetch error:", exc)

    def yahoo_price(symbol):
        payload = _request_json(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            "?range=1d&interval=1d"
        )
        result = payload.get("chart", {}).get("result", [])
        if not result:
            return 0
        meta = result[0].get("meta", {})
        return float(
            meta.get("regularMarketPrice")
            or meta.get("previousClose")
            or 0
        )

    btc_usd = yahoo_price("BTC-USD")
    eth_usd = yahoo_price("ETH-USD")
    if btc_usd <= 0 or eth_usd <= 0 or usd_try <= 0:
        raise ValueError("Yahoo Finance response contains invalid prices")

    return {
        "btc": btc_usd * usd_try,
        "eth": eth_usd * usd_try
    }, "Yahoo Finance"


def _fetch_live_rates():
    errors = []
    fx_rates = None
    fx_source = None
    rate_date = None

    for fetcher in (
        _fetch_tcmb_rates,
        _fetch_frankfurter_rates,
        _fetch_exchange_rate_api,
    ):
        try:
            fx_rates, fx_source, rate_date = fetcher()
            break
        except Exception as exc:
            errors.append(f"{fetcher.__name__}: {exc}")

    if fx_rates is None:
        raise RuntimeError(" | ".join(errors))

    crypto_rates = {}
    crypto_source = "Unavailable"
    try:
        usd_try = 1 / fx_rates["usd"] if fx_rates["usd"] > 0 else 0
        crypto_rates, crypto_source = _fetch_crypto_rates(usd_try)
    except Exception as exc:
        print("Crypto fetch error:", exc)

    return {
        **fx_rates,
        "btc": crypto_rates.get("btc", 0),
        "eth": crypto_rates.get("eth", 0),
        "source": fx_source,
        "crypto_source": crypto_source,
        "rate_date": rate_date,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_live": True,
    }


def get_rates(force_refresh=False):
    now = datetime.now(timezone.utc)

    if not force_refresh and _cache["data"] and _cache["time"]:
        if now - _cache["time"] < timedelta(minutes=CACHE_MINUTES):
            return _cache["data"].copy()

    with _lock:
        if not force_refresh and _cache["data"] and _cache["time"]:
            if now - _cache["time"] < timedelta(minutes=CACHE_MINUTES):
                return _cache["data"].copy()

        try:
            data = _fetch_live_rates()
            _cache["data"] = data
            _cache["time"] = now
            return data.copy()
        except Exception as exc:
            print("All currency providers failed:", exc)

            if _cache["data"]:
                stale = _cache["data"].copy()
                stale["is_live"] = False
                stale["source"] = f'{stale.get("source", "Unknown")} (cached)'
                return stale

            return None
