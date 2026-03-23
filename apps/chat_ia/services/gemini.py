from .base import BaseLLMBackend, LLMError

SYSTEM_PROMPT_TEMPLATE = """
Eres el asistente inteligente de gestión de {org_name}.

Tienes acceso a los datos actuales del sistema de pedidos, \
despachos, clientes, productos, competencia, facturación, \
flotas de transporte y cuotas/ventas de la empresa.

REGLAS ESTRICTAS:
- Responde SIEMPRE en español
- Sé conciso y directo — máximo 3-4 párrafos por respuesta
- Para montos de dinero usa $ y dos decimales (ej: $1,250.00)
- Para fechas usa formato DD/MM/YYYY
- Si no tienes la información exacta en los datos, dilo \
  claramente: "No tengo ese dato en el sistema"
- No inventes pedidos, clientes ni montos que no estén en el contexto
- Si te preguntan algo ajeno al negocio (política, chistes, etc.), \
  responde amablemente que eres un asistente especializado en la \
  gestión de {org_name}
- Cuando listes pedidos o clientes, usa formato de lista clara
- Puedes hacer cálculos simples: sumas, promedios, comparaciones
- Para consultas de cuotas/ventas, incluye siempre el % de cumplimiento
- Para consultas de flotas, incluye el % de utilización del vehículo

DATOS ACTUALES DEL SISTEMA (actualizados en tiempo real):
{context}
"""


class GeminiBackend(BaseLLMBackend):
    MODEL_NAME = 'gemini-2.5-flash'

    def __init__(self):
        import google.generativeai as genai
        from django.conf import settings
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise LLMError(
                'GEMINI_API_KEY no está configurada en las variables de entorno.'
            )
        genai.configure(api_key=api_key)
        self._genai = genai

    def ask(self, pregunta, historial, contexto, org_name):
        try:
            model = self._genai.GenerativeModel(
                model_name=self.MODEL_NAME,
                system_instruction=SYSTEM_PROMPT_TEMPLATE.format(
                    org_name=org_name,
                    context=contexto,
                ),
                generation_config={'max_output_tokens': 1024},
            )
            chat_history = [
                {
                    'role': 'user' if m['rol'] == 'user' else 'model',
                    'parts': [m['contenido']],
                }
                for m in historial
            ]
            chat = model.start_chat(history=chat_history)
            response = chat.send_message(pregunta)
            return response.text
        except Exception as e:
            raise LLMError(f'Error al llamar a Gemini: {e}') from e
