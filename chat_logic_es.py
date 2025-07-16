# chat_logic_es.py

INTENT_KEYWORDS = {
    "nurse": ["dolor", "náusea", "medicamento", "enferma", "picazón", "sangrado", "medicina"],
    "cna": ["agua", "hielo", "baño", "ducha", "ayuda", "limpiar", "almohada", "al asistente de enfermería"],
    "education": ["pregunta", "qué es", "cómo", "puedo", "cuando"],
    "urgent": ["emergencia", "dolor de pecho", "no puedo respirar", "ayúdenme ahora"],
}

EDUCATION_RESPONSES = {
    "showering": "Normalmente puede ducharse, pero por favor consulte primero con su enfermera para ver si tiene alguna restricción.",
    "pumping": "Debería usar el sacaleches cada 2-3 horas para ayudar a establecer su producción de leche. Su enfermera puede solicitar una asesora de lactancia para usted.",
}


def classify_message(message):
    message = message.lower()
    for category, keywords in INTENT_KEYWORDS.items():
        if any(keyword in message for keyword in keywords):
            return category
    return "unknown"


def get_education_response(message):
    message = message.lower()
    if "ducha" in message or "ducharme" in message:
        return EDUCATION_RESPONSES["showering"]
    if "sacaleches" in message or "leche" in message:
        return EDUCATION_RESPONSES["pumping"]

    return "Esa es una buena pregunta. Haré que su enfermera venga a hablar con usted sobre eso."
