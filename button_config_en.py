# button_config_en.py
button_data = {
    # --- Core Notifications & Text ---
    "greeting": "Hello! How can I help you?",
    "custom_note_placeholder": "Type your note to the nurse here...",
    "send_note_button": "Send Note",
    "cna_notification": "✅ CNA has been notified.",
    "nurse_notification": "✅ Nurse has been notified.",
    "back_text": "⬅ Back",
    "demographic_question": "Is this your first baby?",
    "demographic_yes": "Yes",
    "demographic_no": "No",
    "ai_follow_up_question": "Would you like to speak to your nurse?",
    "ai_yes": "Yes, speak to nurse",
    "ai_no": "No, I'm ok",

    # --- Main Menu Options ---
    "main_buttons": [
        "I'm having an emergency",
        "I need supplies",
        "I need medication",
        "My IV pump is beeping",
        "I have questions",
        "I want to know about going home",
        "Bathroom/Shower",
        "I need help breastfeeding",
        "Blood sugar",
        "Ice Chips/Water"
    ],

    # --- Direct Actions & Simple Sub-menus ---
    "I'm having an emergency": {"action": "Notify Nurse"},
    "My IV pump is beeping": {"action": "Notify Nurse"},
    # MODIFIED: Added a video link to this option
    "I need help breastfeeding": {
        "action": "Notify Nurse",
        "note": "✅ Your nurse has been notified. In the meantime, you can prepare by making sure your baby has a clean diaper and is undressed for skin-to-skin contact.",
        "video_link": "https://www.youtube-nocookie.com/embed/AVejyuxHYa0?rel=0",
        "video_text": "Watch a video on Skin-to-Skin"
    },
    "Blood sugar": {
        "question": "Is this for mom or baby?",
        "options": ["Mom (blood sugar)", "Baby (blood sugar)"]
    },
    "Mom (blood sugar)": {"action": "Notify CNA"},
    "Baby (blood sugar)": {"action": "Notify Nurse"},

    "Ice Chips/Water": {
        "question": "If you have a support person with you, they are welcome to go into our nourishment room, which has water, ice chips, juice and small snacks. Staff can show you where it is located. What would you like?",
        "options": [
            "I need ice water",
            "I need ice chips",
            "I need water, no ice",
            "I need hot water"
        ]
    },
    "I need ice water": {"action": "Notify CNA"},
    "I need ice chips": {"action": "Notify CNA"},
    "I need water, no ice": {"action": "Notify CNA"},
    "I need hot water": {"action": "Notify CNA"},

    "Bathroom/Shower": {
        "question": "If you have been up to the bathroom once with a staff member, and you feel steady on your feet, you are able to go to the bathroom on your own. Please let us know if you still need help. What do you need?",
        "options": [
            "I need help to the bathroom",
            "I need my IV covered to shower",
            "Can I take a shower?"
        ]
    },
    "I need help to the bathroom": {"action": "Notify CNA"},
    "I need my IV covered to shower": {"action": "Notify CNA"},
    "Can I take a shower?": {
        "note": "Usually yes, but check with your nurse if you have an IV or other restrictions.",
        "follow_up": True
    },

    # ... (rest of the file is unchanged)
}
