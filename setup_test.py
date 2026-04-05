import datetime
from decimal import Decimal
from apps.accounts.models import User
from apps.cuotas.models import VentaMensual, Zona

sup = User.objects.get(username='mrodriguez')
sup.role = 'supervisor'
sup.save()

ven1 = User.objects.get(username='lgomez')
ven1.supervisor_asignado = sup
ven1.save()

ven2 = User.objects.get(username='asilva')
ven2.supervisor_asignado = sup
ven2.save()

mes_actual = datetime.date.today().replace(day=1)
v = VentaMensual.objects.filter(periodo=mes_actual, vendedor=sup).first()
if not v:
   v = VentaMensual.objects.create(organization=sup.organization, periodo=mes_actual, vendedor=sup, vendedor_nombre=sup.username)
v.plan_venta_usd = Decimal('50000')
v.real_venta_usd = Decimal('32500')
v.save()

for vend, plan, real in [(ven1, '25000', '15000'), (ven2, '25000', '17500')]:
    vm = VentaMensual.objects.filter(periodo=mes_actual, vendedor=vend).first()
    if not vm:
        vm = VentaMensual.objects.create(organization=vend.organization, periodo=mes_actual, vendedor=vend, vendedor_nombre=vend.username)
    vm.plan_venta_usd = Decimal(plan)
    vm.real_venta_usd = Decimal(real)
    vm.save()

print("Setup completed")
