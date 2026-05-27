import requests
from datetime import datetime, timedelta
import threading

_cache = {
    "data": None,
    "time": None
}

CACHE_MIN = 10
_lock = threading.Lock()


def get_rates():
    now = datetime.now()

    # FAST CACHE
    if _cache["data"] and _cache["time"]:
        if now - _cache["time"] < timedelta(minutes=CACHE_MIN):
            return _cache["data"]

    with _lock:

        # DOUBLE CHECK
        if _cache["data"] and _cache["time"]:
            if datetime.now() - _cache["time"] < timedelta(minutes=CACHE_MIN):
                return _cache["data"]

        try:
            # FX API
            fx_res = requests.get(
                "https://api.frankfurter.app/latest?from=TRY&to=USD,EUR,GBP",
                timeout=5
            )
            fx_res.raise_for_status()
            fx = fx_res.json()

            # CRYPTO API
            crypto_res = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=try",
                timeout=5
            )
            crypto_res.raise_for_status()
            crypto = crypto_res.json()

            data = {
                "usd": fx.get("rates", {}).get("USD", 0),
                "eur": fx.get("rates", {}).get("EUR", 0),
                "gbp": fx.get("rates", {}).get("GBP", 0),

                "btc": crypto.get("bitcoin", {}).get("try", 0),
                "eth": crypto.get("ethereum", {}).get("try", 0)
            }

            _cache["data"] = data
            _cache["time"] = datetime.now()

            return data

        except Exception as e:
            print("Currency fetch error:", e)

            if _cache["data"]:
                return _cache["data"]

            return None