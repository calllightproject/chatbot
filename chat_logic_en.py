# This file should contain your logic for classifying messages and providing educational answers.
# The 'education_data' is imported from your education library file.

from education_library_en import education_data

def classify_message(user_input):
    """
    A simplified function to classify user messages based on keywords.
    A real implementation might use more advanced NLP.
    """
    user_input_lower = user_input.lower()
    if any(keyword in user_input_lower for keyword in ["pain", "bleeding", "dizzy", "help", "fever"]):
        return "urgent"
    if any(keyword in user_input_lower for keyword in ["water", "ice", "snack", "food", "pillow", "blanket"]):
        return "cna"
    if any(keyword in user_input_lower for keyword in ["medication", "prescription", "doctor", "discharge"]):
        return "nurse"
    # Check if the input matches any key in the education library
    if any(key in user_input_lower for key in education_data.keys()):
        return "education"
    return "unknown"

def get_education_response(user_input):
    """
    Searches the education library for a response matching the user's input.
    This is the function that was missing.
    """
    user_input_lower = user_input.lower()
    for key, value in education_data.items():
        if key in user_input_lower:
            return value
    return "I'm sorry, I don't have information on that topic. A nurse will be notified."

    return "That's a great question. I'll have your nurse come by to talk with you about it."
