# button_config_bereavement_en.py
button_data = {
    # --- Core Notifications & Text ---
    "greeting": "Hello! We are here to support you.",
    "custom_note_placeholder": "Type your note to the nurse here...",
    "send_note_button": "Send Note",
    "cna_notification": "✅ CNA has been notified.",
    "nurse_notification": "✅ Nurse has been notified.",
    "back_text": "⬅ Back",

# --- Main Menu Options (Bereavement) ---
"main_buttons": [
    "I'm having an emergency",
    "My IV pump is beeping",
    "I need medication",
    "I need supplies",
    "Bathroom/Shower",
    "Ice Chips/Water",
    "I want to see my baby",
    "I need to talk to the social worker",
    "I have questions",
    "I want to know about going home"
],


    # --- Direct Actions & Simple Sub-menus ---
    "I'm having an emergency": {"action": "Notify Nurse"},
    "My IV pump is beeping": {"action": "Notify Nurse"},

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
    "Can I take a shower?": {"note": "Usually yes, but check with your nurse if you have an IV or other restrictions."},

    # --- Supplies Category ---
    "I need supplies": {
        "question": "What do you need?",
        "options": ["Pads", "Mesh underwear", "Ice pack", "Pillows"]
    },
    "Pillows": {"action": "Notify CNA"},
    "Mesh underwear": {"action": "Notify CNA"},
    "Pads": {
        "question": "Which type of pad do you need?",
        "options": ["Blue pads", "White pads"]
    },
    "Blue pads": {"action": "Notify CNA"},
    "White pads": {"action": "Notify CNA"},
    "Ice pack": {
        "question": "Where do you need the ice pack?",
        "options": ["Ice Pack for Bottom", "Ice Pack for C-section incision", "Ice Pack for Breasts"]
    },
    "Ice Pack for Bottom": {"action": "Notify CNA"},
    "Ice Pack for C-section incision": {"action": "Notify CNA"},
    "Ice Pack for Breasts": {"action": "Notify CNA"},

    # --- Medication Category ---
    "I need medication": {
        "question": "What is your main symptom?",
        "options": ["Pain", "Nausea/Vomiting", "Itchy", "Gas pain", "Constipation"]
    },
    "Pain": {"action": "Notify Nurse"},
    "Nausea/Vomiting": {"action": "Notify Nurse"},
    "Itchy": {"action": "Notify Nurse"},
    "Gas pain": {"action": "Notify Nurse"},
    "Constipation": {"action": "Notify Nurse"},

    # --- Questions Category ---
    "I have questions": {
        "note": "If your question is not listed, your nurse will be in as soon as possible.",
        "options": [
            "Can I put on my own clothes?",
            "How often should I change my pad?"
        ]
    },
    "Can I put on my own clothes?": {"note": "Yes, as long as you feel comfortable and have been cleared by your nurse."},
    "How often should I change my pad?": {"note": "Change your pad every 2–4 hours or when it becomes saturated. Let your nurse know if you’re soaking the big pad in less than 1 hour or clots bigger than a golf ball."},

    # --- Going Home Category ---
    "I want to know about going home": {
        "question": "What would you like to know?",
        "options": ["Vaginal delivery", "C-section delivery", "When will I get my discharge paperwork?", "Do I have to take a wheelchair?"]
    },
    "Vaginal delivery": {"note": "If you delivered vaginally, the minimum stay is 24 hours after delivery. An OB-GYN has to give the ok for discharge and update the computer. Typically, as long as your bleeding, blood pressure, and pain are under control, you should be allowed to discharge. However, the OB-GYN makes the final decision."},
    "C-section delivery": {"note": "If you delivered by C-section, the minimum stay is 48 hours. The OB-GYN will give the discharge order if appropriate. Typically, as long as your pain, blood pressure, and bleeding are normal, you will be discharged."},
    "When will I get my discharge paperwork?": {"note": "Once the OB-GYN has put in their notes and discharge orders, your nurse can print out paperwork."},
    "Do I have to take a wheelchair?": {"note": "No, but a staff member has to go with you. If the nursing staff is busy, a transport worker will be the one to escort you out."}
}



