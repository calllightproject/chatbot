# follow_ups.py

# This dictionary defines which button clicks require a follow-up question.
# For each item, we define the question to ask, the options to show,
# and who should be notified (the "action_category").
FOLLOW_UP_CONFIG = {
    "Pads": {
        "type": "pads",
        "question": "Which type of pad do you need?",
        "options": ["Blue pads", "White pads"],
        "action_category": "cna"
    },
    "Formula": {
        "type": "formula",
        "question": "Which formula do you need?",
        "options": [
            "Similac Total Comfort (purple label)",
            "Similac 360 (blue label)",
            "Similac Neosure (yellow label)",
            "Enfamil Newborn (yellow label)",
            "Enfamil Gentlease (purple label)"
        ],
        "action_category": "cna"
    },
    "Ice pack": {
        "type": "ice",
        "question": "Where do you need the ice pack?",
        "options": ["Bottom", "C-section incision", "Breasts"],
        "action_category": "cna"
    },
    "Blood sugar": {
        "type": "blood_sugar",
        "question": "Is this for mom or baby?",
        "options": ["Mom", "Baby (blood sugar)"],
        "action_category": "nurse" # Default, will be overridden for CNA
    }
}

# This dictionary helps the bot remember the original request.
# For example, when the user chooses "Blue pads", this map tells the bot
# that "Blue pads" is an answer to the "pads" question.
# Copy this entire dictionary and use it to replace the old one.

RESPONSE_TO_TYPE_MAP = {
    "Blue pads": "Pads",  # Changed "pads" to "Pads"
    "White pads": "Pads", # Changed "pads" to "Pads"
    "Similac Total Comfort (purple label)": "Formula", # Changed "formula" to "Formula"
    "Similac 360 (blue label)": "Formula", # Changed "formula" to "Formula"
    "Similac Neosure (yellow label)": "Formula", # Changed "formula" to "Formula"
    "Enfamil Newborn (yellow label)": "Formula", # Changed "formula" to "Formula"
    "Enfamil Gentlease (purple label)": "Formula", # Changed "formula" to "Formula"
    "Bottom": "Ice pack",
    "C-section incision": "Ice pack",
    "Breasts": "Ice pack",
    "Mom": "Blood sugar",
    "Baby (blood sugar)": "Blood sugar",
}

def get_follow_up_question(user_input):
    """Checks if a user's button click needs a follow-up question."""
    return FOLLOW_UP_CONFIG.get(user_input)

def handle_follow_up_response(user_input):
    """
    Handles the user's answer to a follow-up question and decides who to notify.
    """
    # First, check if the user's input is a known follow-up answer
    if user_input in RESPONSE_TO_TYPE_MAP:
        # Determine who to notify based on the answer
        if user_input == "Mom": # Special case for blood sugar
            category = "cna"
        else:
            original_request_type = RESPONSE_TO_TYPE_MAP[user_input]
            category = FOLLOW_UP_CONFIG[original_request_type]["action_category"]

        return {
            "reply": f"✅ {category.upper()} has been notified.",
            "category": category
        }
    return None # Return None if it's not a follow-up response