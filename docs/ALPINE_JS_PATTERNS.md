# Patrones Alpine.js para SmartSales

Guía de referencia rápida de los patrones Alpine.js usados en el proyecto.

---

## 1. Modal genérico

```html
<!-- Usar en cualquier modal del sistema -->
<div x-data="{ open: false }">

  <!-- Botón de apertura -->
  <button @click="open = true" class="btn-primary">
    + Nuevo Pedido
  </button>

  <!-- Overlay y modal -->
  <div
    x-show="open"
    x-transition:enter="transition ease-out duration-200"
    x-transition:enter-start="opacity-0"
    x-transition:enter-end="opacity-100"
    x-transition:leave="transition ease-in duration-150"
    x-transition:leave-start="opacity-100"
    x-transition:leave-end="opacity-0"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    @click.self="open = false"
    @keydown.escape.window="open = false"
  >
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between p-6 border-b">
        <h3 class="font-bold text-lg">Nuevo Pedido</h3>
        <button @click="open = false" class="text-slate-400 hover:text-slate-600">✕</button>
      </div>
      <div class="p-6">
        <!-- Contenido del modal -->
      </div>
    </div>
  </div>
</div>
```

---

## 2. Formulario de pedido con ítems dinámicos

```html
<div x-data="pedidoForm()">

  <!-- Lista de ítems -->
  <div class="space-y-3">
    <template x-for="(item, index) in items" :key="index">
      <div class="grid grid-cols-12 gap-2 items-end">
        <div class="col-span-5">
          <label class="text-xs text-slate-500">Producto</label>
          <input type="text" x-model="item.producto" name="items[][producto]"
                 class="input-base" placeholder="Nombre del producto">
        </div>
        <div class="col-span-2">
          <label class="text-xs text-slate-500">SKU</label>
          <input type="text" x-model="item.sku" name="items[][sku]"
                 class="input-base" placeholder="Opcional">
        </div>
        <div class="col-span-2">
          <label class="text-xs text-slate-500">Cantidad</label>
          <input type="number" x-model.number="item.cantidad" name="items[][cantidad]"
                 class="input-base" min="0.01" step="0.01">
        </div>
        <div class="col-span-2">
          <label class="text-xs text-slate-500">Precio</label>
          <input type="number" x-model.number="item.precio" name="items[][precio]"
                 class="input-base" min="0" step="0.01">
        </div>
        <div class="col-span-1">
          <button @click="quitarItem(index)"
                  x-show="items.length > 1"
                  type="button"
                  class="text-red-400 hover:text-red-600 p-2">✕</button>
        </div>
      </div>
    </template>
  </div>

  <!-- Botón agregar ítem -->
  <button @click="agregarItem()" type="button"
          class="mt-3 text-sm text-brand hover:text-blue-700 font-medium">
    + Agregar ítem
  </button>

  <!-- Total en tiempo real -->
  <div class="mt-4 text-right">
    <span class="text-slate-500 text-sm">Total:</span>
    <span class="text-xl font-bold text-slate-900 ml-2"
          x-text="'$' + total().toFixed(2)">$0.00</span>
  </div>

</div>

<script>
function pedidoForm(itemsIniciales = null) {
  return {
    items: itemsIniciales || [{ producto: '', sku: '', cantidad: 1, precio: 0 }],

    agregarItem() {
      this.items.push({ producto: '', sku: '', cantidad: 1, precio: 0 })
    },

    quitarItem(index) {
      if (this.items.length > 1) {
        this.items.splice(index, 1)
      }
    },

    total() {
      return this.items.reduce((sum, item) => {
        return sum + (parseFloat(item.cantidad) || 0) * (parseFloat(item.precio) || 0)
      }, 0)
    },
  }
}
</script>
```

---

## 3. Filtro de búsqueda en tiempo real

```html
<!-- Para tablas que NO usan HTMX (filtrado local) -->
<div x-data="{ busqueda: '' }">
  <input
    type="text"
    x-model="busqueda"
    placeholder="Buscar cliente, pedido..."
    class="input-base"
  >

  <table>
    <tbody>
      {% for pedido in pedidos %}
      <tr x-show="
            '{{ pedido.numero }}'.toLowerCase().includes(busqueda.toLowerCase()) ||
            '{{ pedido.cliente }}'.toLowerCase().includes(busqueda.toLowerCase()) ||
            '{{ pedido.vendedor }}'.toLowerCase().includes(busqueda.toLowerCase())
          ">
        <!-- celdas -->
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

---

## 4. Confirmación de eliminación

```html
<button
  @click="if(confirm('¿Eliminar este pedido? Esta acción no se puede deshacer.')) $refs.formEliminar.submit()"
  type="button"
  class="text-red-500 hover:text-red-700 text-sm"
>
  Eliminar
</button>
<form x-ref="formEliminar" method="post" action="{% url 'pedidos:eliminar' pedido.pk %}">
  {% csrf_token %}
</form>
```

---

## 5. Tabs sin JavaScript framework

```html
<div x-data="{ tab: 'pendientes' }">

  <!-- Cabeceras de tabs -->
  <div class="flex gap-1 border-b border-slate-200 mb-4">
    <button @click="tab = 'pendientes'"
            :class="tab === 'pendientes' ? 'border-b-2 border-brand text-brand' : 'text-slate-500'"
            class="px-4 py-2 text-sm font-medium transition-colors">
      Pendientes
    </button>
    <button @click="tab = 'programados'"
            :class="tab === 'programados' ? 'border-b-2 border-brand text-brand' : 'text-slate-500'"
            class="px-4 py-2 text-sm font-medium transition-colors">
      Programados
    </button>
  </div>

  <!-- Contenido de tabs -->
  <div x-show="tab === 'pendientes'">
    <!-- contenido pendientes -->
  </div>
  <div x-show="tab === 'programados'">
    <!-- contenido programados -->
  </div>

</div>
```

---

## 6. Notificación / Toast

```html
<!-- En base.html, siempre presente -->
<div
  x-data="toastManager()"
  x-on:show-toast.window="show($event.detail)"
  class="fixed bottom-4 right-4 z-50 space-y-2"
>
  <template x-for="toast in toasts" :key="toast.id">
    <div
      x-show="toast.visible"
      x-transition:enter="transform transition ease-out duration-300"
      x-transition:enter-start="translate-y-2 opacity-0"
      x-transition:enter-end="translate-y-0 opacity-100"
      x-transition:leave="transition ease-in duration-200"
      x-transition:leave-end="opacity-0"
      :class="toast.type === 'error' ? 'bg-red-600' : 'bg-green-600'"
      class="text-white px-4 py-3 rounded-lg shadow-lg text-sm font-medium min-w-[200px]"
      x-text="toast.message"
    ></div>
  </template>
</div>

<script>
function toastManager() {
  return {
    toasts: [],
    show({ message, type = 'success', duration = 3000 }) {
      const id = Date.now()
      this.toasts.push({ id, message, type, visible: true })
      setTimeout(() => {
        const t = this.toasts.find(t => t.id === id)
        if (t) t.visible = false
        setTimeout(() => {
          this.toasts = this.toasts.filter(t => t.id !== id)
        }, 300)
      }, duration)
    }
  }
}

// Disparar desde cualquier lugar:
// window.dispatchEvent(new CustomEvent('show-toast', { detail: { message: '¡Pedido guardado!', type: 'success' } }))
// O desde HTMX con hx-on::after-request
</script>
```

---

## 7. Integración HTMX + Alpine.js

```html
<!-- HTMX para filtrar tabla sin recargar la página -->
<input
  type="text"
  name="q"
  hx-get="{% url 'pedidos:lista' %}"
  hx-trigger="keyup changed delay:300ms"
  hx-target="#tabla-pedidos"
  hx-swap="innerHTML"
  placeholder="Buscar..."
  class="input-base"
>

<div id="tabla-pedidos">
  {% include 'partials/tabla_pedidos.html' %}
</div>
```

```python
# views.py — respuesta parcial para HTMX
def lista_pedidos(request):
    q = request.GET.get('q', '')
    pedidos = Pedido.objects.filter(
        organization=request.org
    ).select_related('cliente', 'vendedor')

    if q:
        pedidos = pedidos.filter(
            models.Q(numero__icontains=q) |
            models.Q(cliente__nombre__icontains=q) |
            models.Q(vendedor__first_name__icontains=q)
        )

    if request.htmx:
        # Solo retorna el fragmento de la tabla
        return render(request, 'partials/tabla_pedidos.html', {'pedidos': pedidos})

    return render(request, 'pedidos/lista.html', {'pedidos': pedidos})
```
