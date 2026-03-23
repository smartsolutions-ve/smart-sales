import logging
from .base import BaseLLMBackend, LLMError
from .gemini import SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger('chat_ia')

FALLBACK_MODELS = [
    'google/gemma-3-12b-it:free',
    'arcee-ai/trinity-large-preview:free',
    'qwen/qwen3-4b:free',
    'nvidia/nemotron-nano-9b-v2:free',
    'google/gemma-3-4b-it:free',
]


class OpenRouterBackend(BaseLLMBackend):

    def __init__(self):
        from openai import OpenAI
        from django.conf import settings
        api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
        if not api_key:
            raise LLMError('OPENROUTER_API_KEY no configurada.')
        self.model = getattr(settings, 'OPENROUTER_MODEL', 'google/gemma-3-27b-it:free')
        self.client = OpenAI(
            base_url='https://openrouter.ai/api/v1',
            api_key=api_key,
            max_retries=0,
            timeout=25.0,
        )

    def _build_messages(self, pregunta, historial, contexto, org_name):
        system_content = SYSTEM_PROMPT_TEMPLATE.format(
            org_name=org_name, context=contexto,
        )
        messages = [{'role': 'system', 'content': system_content}]
        for m in historial:
            messages.append({
                'role': 'user' if m['rol'] == 'user' else 'assistant',
                'content': m['contenido'],
            })
        messages.append({'role': 'user', 'content': pregunta})
        return messages

    def _call(self, model, messages):
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            extra_headers={
                'HTTP-Referer': 'https://smartsales.com.ve',
                'X-Title': 'SmartSales Chat IA',
            },
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMError(f'{model} devolvió respuesta vacía.')
        return content

    def ask(self, pregunta, historial, contexto, org_name):
        messages = self._build_messages(pregunta, historial, contexto, org_name)
        models = [self.model] + [f for f in FALLBACK_MODELS if f != self.model]
        last_error = None

        for model in models:
            try:
                logger.info('Chat IA: intentando modelo %s', model)
                result = self._call(model, messages)
                logger.info('Chat IA: respuesta OK de %s', model)
                return result
            except Exception as e:
                last_error = e
                logger.warning('Chat IA: %s falló: %s', model, str(e)[:120])
                continue

        raise LLMError(f'Todos los modelos fallaron. Último error: {last_error}')
