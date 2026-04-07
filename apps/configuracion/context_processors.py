def tasa_cambio(request):
    """Inyecta tasa_cambio y mostrar_bs en todos los templates."""
    if not getattr(request, 'org', None):
        return {'tasa_cambio': None, 'mostrar_bs': False}
    from .models import TasaCambio
    tasa = TasaCambio.activa_para(request.org)
    return {'tasa_cambio': tasa, 'mostrar_bs': tasa is not None}
