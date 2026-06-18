from decimal import Decimal, InvalidOperation

from django import template

from core.utils.rates import get_usd_rate

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


@register.filter(name="clp_to_usd")
def clp_to_usd(value, digits=2):
    """Convierte CLP a USD según tipo de cambio."""
    clp_val = _to_decimal(value)
    rate = get_usd_rate()
    try:
        rate = Decimal(str(rate))
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"

    if rate == 0:
        return "0.00"

    usd = clp_val * rate
    fmt = f"{{:.{int(digits)}f}}"
    return fmt.format(usd)


@register.filter(name="mul")
def mul(value, arg):
    """Multiplica dos números de forma segura (Decimal)."""
    return _to_decimal(value) * _to_decimal(arg)
