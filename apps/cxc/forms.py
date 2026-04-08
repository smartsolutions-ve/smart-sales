"""
Formularios del módulo de Cuentas por Cobrar.
"""
from django import forms

from .models import Pago


class PagoForm(forms.ModelForm):
    """Formulario para registrar un pago de cliente."""

    class Meta:
        model = Pago
        fields = ['fecha', 'monto', 'metodo', 'referencia', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(
                attrs={'type': 'date', 'class': 'input-base'},
            ),
            'monto': forms.NumberInput(
                attrs={'class': 'input-base', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'},
            ),
            'metodo': forms.Select(
                attrs={'class': 'input-base'},
            ),
            'referencia': forms.TextInput(
                attrs={'class': 'input-base', 'placeholder': 'N° de comprobante (opcional)'},
            ),
            'observaciones': forms.Textarea(
                attrs={'class': 'input-base', 'rows': 2, 'placeholder': 'Observaciones (opcional)'},
            ),
        }
        labels = {
            'fecha': 'Fecha de pago',
            'monto': 'Monto (USD)',
            'metodo': 'Método de pago',
            'referencia': 'Referencia / Comprobante',
            'observaciones': 'Observaciones',
        }
