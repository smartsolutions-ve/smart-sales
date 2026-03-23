# Chat IA — Manual de Uso y Cambio de Proveedores

## Cambio rápido entre IAs

El proveedor de IA se controla 100% desde el archivo `.env`. No necesitas tocar código.

### Opción 1: Google Gemini (actual)

```env
CHAT_IA_BACKEND=apps.chat_ia.services.gemini.GeminiBackend
GEMINI_API_KEY=tu-clave-aqui
```

- API key: https://aistudio.google.com/apikeys
- Modelo usado: `gemini-2.0-flash`
- Costo: tier gratuito generoso, luego ~$0.10/1M tokens
- SDK: `google-generativeai` (ya instalado)

### Opción 2: OpenRouter (modelos gratuitos o de pago)

```env
CHAT_IA_BACKEND=apps.chat_ia.services.openrouter.OpenRouterBackend
OPENROUTER_API_KEY=sk-or-v1-tu-clave
OPENROUTER_MODEL=google/gemma-3-27b-it:free
```

- API key: https://openrouter.ai/keys
- Modelos gratuitos: terminan en `:free` (tienen rate limits)
- SDK: `openai` (ya instalado)
- Si el modelo elegido falla, intenta automáticamente con fallbacks

**Cambiar de modelo**: solo edita `OPENROUTER_MODEL` en `.env` y reinicia el servidor.

### Opción 3: OpenAI (GPT-4o)

Requiere crear el archivo `apps/chat_ia/services/openai_backend.py` (código abajo).

```env
CHAT_IA_BACKEND=apps.chat_ia.services.openai_backend.OpenAIBackend
OPENAI_API_KEY=sk-...
```

Agregar en `config/settings/base.py`:
```python
OPENAI_API_KEY = env('OPENAI_API_KEY', default='')
```

Crear `apps/chat_ia/services/openai_backend.py`:
```python
from .base import BaseLLMBackend, LLMError
from .gemini import SYSTEM_PROMPT_TEMPLATE


class OpenAIBackend(BaseLLMBackend):
    MODEL_NAME = 'gpt-4o-mini'

    def __init__(self):
        from openai import OpenAI
        from django.conf import settings
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise LLMError('OPENAI_API_KEY no configurada.')
        self.client = OpenAI(api_key=api_key, max_retries=0, timeout=25.0)

    def ask(self, pregunta, historial, contexto, org_name):
        try:
            messages = [
                {'role': 'system', 'content': SYSTEM_PROMPT_TEMPLATE.format(
                    org_name=org_name, context=contexto)},
            ]
            for m in historial:
                messages.append({
                    'role': 'user' if m['rol'] == 'user' else 'assistant',
                    'content': m['contenido'],
                })
            messages.append({'role': 'user', 'content': pregunta})

            response = self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMError(f'Error OpenAI: {e}') from e
```

### Opción 4: Anthropic (Claude)

```bash
pip install anthropic
```

```env
CHAT_IA_BACKEND=apps.chat_ia.services.anthropic_backend.AnthropicBackend
ANTHROPIC_API_KEY=sk-ant-...
```

Agregar en `config/settings/base.py`:
```python
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default='')
```

Crear `apps/chat_ia/services/anthropic_backend.py`:
```python
from .base import BaseLLMBackend, LLMError
from .gemini import SYSTEM_PROMPT_TEMPLATE


class AnthropicBackend(BaseLLMBackend):
    MODEL_NAME = 'claude-sonnet-4-6'

    def __init__(self):
        import anthropic
        from django.conf import settings
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise LLMError('ANTHROPIC_API_KEY no configurada.')
        self.client = anthropic.Anthropic(api_key=api_key)

    def ask(self, pregunta, historial, contexto, org_name):
        try:
            system = SYSTEM_PROMPT_TEMPLATE.format(
                org_name=org_name, context=contexto)
            messages = []
            for m in historial:
                messages.append({
                    'role': 'user' if m['rol'] == 'user' else 'assistant',
                    'content': m['contenido'],
                })
            messages.append({'role': 'user', 'content': pregunta})

            response = self.client.messages.create(
                model=self.MODEL_NAME, system=system,
                messages=messages, max_tokens=1024,
            )
            return response.content[0].text
        except Exception as e:
            raise LLMError(f'Error Anthropic: {e}') from e
```

---

## Pasos para cambiar de proveedor

1. Editar `.env`:
   - Cambiar `CHAT_IA_BACKEND=...` al backend deseado
   - Poner la API key correspondiente
2. Reiniciar el servidor: `python manage.py runserver`
3. Listo. No se necesita migración ni cambio de código.

---

## Consumo de tokens por request

Cada pregunta del usuario consume tokens así:

| Componente | Tokens aprox. | Notas |
|---|---|---|
| System prompt | ~200 | Reglas del asistente (fijo) |
| Contexto de la BD | 500-6,000 | Depende de cuántos datos tenga la org |
| Historial (hasta 10 msgs) | 0-2,500 | Se trunca a 500 chars por mensaje |
| Pregunta del usuario | 10-150 | Máximo 500 caracteres |
| **Total entrada** | **~700-8,800** | |
| Respuesta del LLM | 100-1,024 | Limitado a 1,024 tokens |

### Medidas anti-fuga implementadas

- **`max_output_tokens: 1024`** en todos los backends — la IA no puede generar respuestas infinitas
- **Historial truncado a 500 chars/msg** — evita reenviar respuestas largas
- **Contexto máximo 24,000 chars** — truncado si la org tiene muchos datos
- **Rate limit: 30 preguntas/hora** por usuario — previene abuso
- **`max_retries=0` + `timeout=25s`** en OpenRouter — falla rápido, no gasta tokens en reintentos
- **Management command `limpiar_chat --dias 90`** — borra mensajes viejos de la BD

### Estimación de costos mensuales

Asumiendo 50 preguntas/día con contexto medio (~3,000 tokens entrada + ~500 tokens respuesta):

| Proveedor | Modelo | Costo/mes estimado |
|---|---|---|
| Gemini | gemini-2.0-flash | ~$0.50 |
| OpenRouter | modelos :free | $0 (con rate limits) |
| OpenAI | gpt-4o-mini | ~$1.50 |
| OpenAI | gpt-4o | ~$15.00 |
| Anthropic | claude-haiku | ~$1.00 |
| Anthropic | claude-sonnet | ~$15.00 |

---

## Modelos gratuitos de OpenRouter

Los modelos `:free` rotan frecuentemente. Para ver los disponibles:

```bash
# Listar modelos gratuitos actuales
python manage.py shell -c "
from openai import OpenAI
from django.conf import settings
client = OpenAI(base_url='https://openrouter.ai/api/v1', api_key=settings.OPENROUTER_API_KEY)
for m in sorted(m.id for m in client.models.list().data if ':free' in m.id):
    print(m)
"
```

### Recomendados (marzo 2026)

| Modelo | ID | Calidad | Velocidad |
|---|---|---|---|
| Gemma 3 27B | `google/gemma-3-27b-it:free` | Buena | Rápido |
| Trinity Large | `arcee-ai/trinity-large-preview:free` | Buena | Medio |
| Qwen3 Coder | `qwen/qwen3-coder:free` | Media | Rápido |
| Gemma 3 12B | `google/gemma-3-12b-it:free` | Media | Muy rápido |

---

## Crear un backend personalizado

Solo implementa la interfaz `BaseLLMBackend`:

```python
# apps/chat_ia/services/mi_backend.py
from .base import BaseLLMBackend, LLMError

class MiBackend(BaseLLMBackend):
    def ask(self, pregunta: str, historial: list[dict],
            contexto: str, org_name: str) -> str:
        # pregunta: texto del usuario (max 500 chars)
        # historial: [{'rol': 'user'|'assistant', 'contenido': '...'}]
        # contexto: resumen de datos de la org (puede ser largo)
        # org_name: nombre de la organización
        # Debe retornar un string con la respuesta
        ...
```

```env
CHAT_IA_BACKEND=apps.chat_ia.services.mi_backend.MiBackend
```

---

## Diagnóstico de problemas

Los errores del chat se logean en la consola del servidor con el logger `chat_ia`.

Errores comunes:

| Error | Causa | Solución |
|---|---|---|
| `OPENROUTER_API_KEY no configurada` | Falta la key en `.env` | Agregar la key |
| `429 Rate limit` | Cuota agotada | Esperar o cambiar de proveedor |
| `404 No endpoints found` | Modelo no existe | Cambiar `OPENROUTER_MODEL` |
| `400 Bad Request` | Modelo no soporta system messages | Cambiar de modelo |
| `Todos los modelos fallaron` | Todos los fallbacks agotados | Esperar o usar Gemini |
| Timeout | El modelo tardó >25s | Reintentar o cambiar modelo |
