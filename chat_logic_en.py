# chat_logic_en.py
from education_library_en import education_data, education_keywords

INTENT_KEYWORDS = {
    "nurse": ["pain", "nausea", "medication", "sick", "itchy", "bleeding", "medicine", "dizzy"],
    "cna": ["water", "ice", "bathroom", "shower", "help", "clean", "pillow", "walk"],
    "education": ["question", "what about", "tell me about", "how do", "can i", "when"],
    "urgent": ["emergency", "chest pain", "can't breathe", "help me now", "bleeding heavily"],
}


def classify_message(message):
    """ Classifies the user's message into a category based on keywords. """
    message = message.lower()
    for category, keywords in INTENT_KEYWORDS.items():
        if any(keyword in message for keyword in keywords):
            return category
    # If no category keywords are found, check for education keywords
    for keyword in education_keywords:
        if keyword in message:
            return "education"
    return "unknown"


def get_education_response(message):
    """ Finds a relevant educational response from the library. """
    message = message.lower()
    # Search for a keyword from the user's message in our education_keywords dictionary
    for keyword, topic_key in education_keywords.items():
        if keyword in message:
            return education_data[topic_key]

    # A default response if no specific topic is found
    return "That's a great question. I'll have your nurse come by to talk with you about it."