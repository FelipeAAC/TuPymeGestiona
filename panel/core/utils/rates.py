import json
import time
from django.core.cache import cache
from django.conf import settings

try:
    import requests
except Exception:
    requests = None

CACHE_KEY = "clp_usd_rate"
TTL = getattr(settings, "EXCHANGE_RATE_TTL", 60 * 30)

def _fetch_rate_from_api():
    url = getattr(settings, "EXCHANGE_RATE_PROVIDER_URL",
                  "https://api.exchangerate.host/latest?base=CLP&symbols=USD")
    if not requests:
        return None
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        data = r.json()
        return float(data["rates"]["USD"])
    except Exception:
        return None

def get_usd_rate():
    """
    Devuelve la tasa USD/CLP: cuántos dólares vale 1 peso chileno.
    """
    rate = cache.get(CACHE_KEY)
    if rate is not None:
        return rate

    rate = _fetch_rate_from_api()
    if rate is not None:
        cache.set(CACHE_KEY, rate, TTL)
        return rate

    default_clp_per_usd = float(getattr(settings, "EXCHANGE_RATE_DEFAULT", 950.0))
    if default_clp_per_usd == 0:
        return 0.0
    return 1.0 / default_clp_per_usd
