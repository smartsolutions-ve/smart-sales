from decimal import Decimal, ROUND_HALF_UP
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def en_bs(context, valor_usd):
    """Retorna el valor en Bs como Decimal, o None si no hay tasa."""
    tasa = context.get('tasa_cambio')
    if tasa and valor_usd is not None:
        try:
            return (Decimal(str(valor_usd)) * tasa.tasa).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        except Exception:
            pass
    return None


@register.inclusion_tag('configuracion/_monto_dual.html', takes_context=True)
def monto_dual(context, valor_usd, clase='', bloque=False):
    """
    Muestra monto USD con equivalente Bs si hay tasa configurada.
    bloque=True para layout vertical (en cards), False para inline (en tablas).
    """
    tasa = context.get('tasa_cambio')
    valor_bs = None
    if tasa and valor_usd is not None:
        try:
            valor_bs = (Decimal(str(valor_usd)) * tasa.tasa).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        except Exception:
            pass
    return {'valor_usd': valor_usd, 'valor_bs': valor_bs, 'clase': clase, 'bloque': bloque}
