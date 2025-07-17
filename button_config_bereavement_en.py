# button_config_bereavement_en.py
button_data = {
    "greeting": "Hello! We are here to support you.",  # Changed greeting to be more sensitive
    "cna_notification": "✅ CNA has been notified.",
    "nurse_notification": "✅ Nurse has been notified.",
    "back_text": "⬅ Back",
    "main_buttons": [
        "I'm having an emergency",
        "I need supplies",
        "I need medication",
        "I have questions",
        "I want to know about going home",
        "I need help to the bathroom",
        "I need my IV covered to shower",
        "Blood sugar check for me"
    ],

    "I'm having an emergency": {"action": "Notify Nurse"},
    "I need help to the bathroom": {"action": "Notify CNA"},
    "I need my IV covered to shower": {"action": "Notify CNA"},

    "Blood sugar check for me": {"action": "Notify CNA"},

    "I need supplies": {
        "question": "What do you need?",
        "options": ["Pads", "Mesh underwear", "Ice pack"]
    },
    "Pads": {
        "question": "Which type of pad do you need?",
        "options": ["Blue pads", "White pads"]
    },
    "Blue pads": {"action": "Notify CNA"},
    "White pads": {"action": "Notify CNA"},

    "Ice pack": {
        "question": "Where do you need the ice pack?",
        "options": ["Bottom", "C-section incision", "Breasts"]
    },
    "Bottom": {"action": "Notify CNA"},
    "C-section incision": {"action": "Notify CNA"},
    "Breasts": {"action": "Notify CNA"},

    "Mesh underwear": {"action": "Notify CNA"},

    "I need medication": {
        "question": "What is your main symptom?",
        "options": ["Pain", "Nausea/Vomiting", "Itchy", "Gas pain", "Constipation"]
    },
    "Pain": {"action": "Notify Nurse"},
    "Nausea/Vomiting": {"action": "Notify Nurse"},
    "Itchy": {"action": "Notify Nurse"},
    "Gas pain": {"action": "Notify Nurse"},
    "Constipation": {"action": "Notify Nurse"}, # <-- The comma was missing here

    "I have questions": {
        "note": "If your question is not listed, your nurse will be in as soon as possible.",
        "options": [
            "Can I take a shower?",
            "Can I put on my own clothes?",
            "How often should I change my pad?",
        ]
    },
    "Can I take a shower?": {
        "note": "Usually yes, but check with your nurse if you have an IV or other restrictions."
    },
    "Can I put on my own clothes?": {
        "note": "Yes, as long as you feel comfortable and have been cleared by your nurse."
    },
    "How often should I change my pad?": {
        "note": "Change your pad every 2–4 hours or when it becomes saturated. Let your nurse know if you’re soaking the big pad in less than 1 hour or clots bigger than a golf ball."
    },

    "I want to know about going home": {
        "question": "What would you like to know?",
        "options": ["Vaginal delivery", "C-section delivery", "When will I get my discharge paperwork?",
                    "Do I have to take a wheelchair?"]
    },
    "When will I get my discharge paperwork?": {
        "note": "Once the OB-GYN has put in their notes and discharge orders, your nurse can print out paperwork."
    },
    "Do I have to take a wheelchair?": {
        "note": "No, but a staff member has to go with you. If the nursing staff is busy, a transport worker will be the one to escort you out."
    },
    "Vaginal delivery": {
        "note": "If you delivered vaginally, the minimum stay is 24 hours after delivery. An OB-GYN has to give the ok for discharge and update the computer. Typically, as long as your bleeding, blood pressure, and pain are under control, you should be allowed to discharge. However, the OB-GYN makes the final decision."
    },
    "C-section delivery": {
        "note": "If you delivered by C-section, the minimum stay is 48 hours. The OB-GYN will give the discharge order if appropriate. Typically, as long as your pain, blood pressure, and bleeding are normal, you will be discharged."
    }
}
