from django import template
from django.conf import settings
from django.core.cache import cache
from decimal import Decimal, InvalidOperation
import json
import urllib.request

register = template.Library()

def _to_decimal(val):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")

def _format_clp(val: Decimal) -> str:
    n = int(val.quantize(Decimal("1")))
    s = f"{n:,}".replace(",", ".")
    return f"${s}"

@register.filter(name="clp")
def clp(value):
    """Formatea CLP: $1.234.567"""
    return _format_clp(_to_decimal(value))

def _get_usd_rate() -> Decimal:
    """
    Intenta leer un tipo de cambio CLP->USD desde cache o API.
    Fallback a settings.EXCHANGE_RATE_DEFAULT si algo falla.
    """
    cache_key = "clp_usd_rate"
    cached = cache.get(cache_key)
    if cached:
        try:
            return Decimal(str(cached))
        except InvalidOperation:
            pass

    rate = None
    url = getattr(settings, "EXCHANGE_RATE_PROVIDER_URL", None)
    ttl = getattr(settings, "EXCHANGE_RATE_TTL", 1800)
    default = getattr(settings, "EXCHANGE_RATE_DEFAULT", 950.0)

    try:
        if url:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                rate = Decimal(str(data["rates"]["USD"]))
    except Exception:
        rate = None

    if rate is None:
        rate = Decimal(str(default))

    cache.set(cache_key, str(rate), ttl)
    return rate

@register.filter(name="clp_to_usd")
def clp_to_usd(value, digits=2):
    """
    Convierte CLP a USD según tipo de cambio.
    Retorna string con 2 decimales por defecto.
    """
    clp_val = _to_decimal(value)
    rate = _get_usd_rate()
    if rate == 0:
        return "0.00"
    usd = clp_val / rate
    fmt = f"{{:.{int(digits)}f}}"
    return fmt.format(usd)

@register.filter(name="mul")
def mul(value, arg):
    """Multiplica dos números de forma segura (Decimal)."""
    return _to_decimal(value) * _to_decimal(arg)
