# button_config_en.py
button_data = {
    "greeting": "Hello! How can I help you?",
    "custom_note_placeholder": "Type your note to the nurse here...",
    "submit_button": "Submit Selections",
    "confirmation_message": "Your requests have been sent.",
    "selection_prompt": "Please select one or more items.",
    "send_note_button": "Send Note",
    "cna_notification": "✅ CNA has been notified.",
    "nurse_notification": "✅ Nurse has been notified.",
    "main_buttons": [
        "I'm having an emergency",
        "I need supplies",
        "I need medication",
        "I have questions",
        "I want to know about going home",
        "I need help to the bathroom",
        "I need my IV covered to shower",
        "I need help breastfeeding",
        "Blood sugar"
    ],

    "I'm having an emergency": {"action": "Notify Nurse"},
    "I need help to the bathroom": {"action": "Notify CNA"},
    "I need my IV covered to shower": {"action": "Notify CNA"},
    "I need help breastfeeding": {
        "action": "Notify Nurse",
        "note": "✅ Your nurse has been notified. In the meantime, you can prepare by making sure your baby has a clean diaper and is undressed for skin-to-skin contact."
    },

    "Blood sugar": {
        "question": "Is this for mom or baby?",
        "options": ["Mom", "Baby (blood sugar)"]
    },
    "Mom": {"action": "Notify CNA"},
    "Baby (blood sugar)": {"action": "Notify Nurse"},

    "I need supplies": {
        "question": "For baby or mom?",
        "options": ["Baby items", "Mom items"]
    },
    "Baby items": {"question": "What does your baby need?", "options": ["Diapers", "Formula", "Swaddle", "Wipes"]},
    "Mom items": {"question": "What do you need?", "options": ["Pads", "Mesh underwear", "Ice pack"]},
    # ... other supply options ...
    "Diapers": {"action": "Notify CNA"},
    "Swaddle": {"action": "Notify CNA"},
    "Wipes": {"action": "Notify CNA"},
    "Mesh underwear": {"action": "Notify CNA"},
    "Pads": {"question": "Which type of pad do you need?", "options": ["Blue pads", "White pads"]},
    "Blue pads": {"action": "Notify CNA"},
    "White pads": {"action": "Notify CNA"},
    "Ice pack": {"question": "Where do you need the ice pack?", "options": ["Bottom", "C-section incision", "Breasts"]},
    "Bottom": {"action": "Notify CNA"},
    "C-section incision": {"action": "Notify CNA"},
    "Breasts": {"action": "Notify CNA"},
    "Formula": {"question": "Which formula do you need?",
                "options": ["Similac Total Comfort (purple label)", "Similac 360 (blue label)",
                            "Similac Neosure (yellow label)", "Enfamil Newborn (yellow label)",
                            "Enfamil Gentlease (purple label)"]},
    "Similac Total Comfort (purple label)": {"action": "Notify CNA"},
    "Similac 360 (blue label)": {"action": "Notify CNA"},
    "Similac Neosure (yellow label)": {"action": "Notify CNA"},
    "Enfamil Newborn (yellow label)": {"action": "Notify CNA"},
    "Enfamil Gentlease (purple label)": {"action": "Notify CNA"},

    "I need medication": {
        "question": "What is your main symptom?",
        "options": ["Pain", "Nausea/Vomiting", "Itchy", "Gas pain", "Constipation"]
    },

    "Nausea/Vomiting": {"action": "Notify Nurse"},
    "Itchy": {"action": "Notify Nurse"},
    "Gas pain": {"action": "Notify Nurse"},
    "Constipation": {"action": "Notify Nurse"},

    "I have questions": {
        "question": "Questions about mom or baby?",
        "options": ["Questions about mom", "Questions about baby"]
    },
    # ... other questions ...
    "Questions about mom": {"note": "If your question is not listed, your nurse will be in as soon as possible.",
                            "options": ["Can I take a shower?", "Can I put on my own clothes?",
                                        "How often should I change my pad?", "How often should I use the breast pump?",
                                        "I'm not getting any breastmilk when I pump. Is that normal?"]},
    "Questions about baby": {"note": "If your question is not listed, your nurse will be in as soon as possible.",
                             "options": ["How often should I feed my baby?",
                                         "I'm concerned that my baby is not getting enough breastmilk.",
                                         "My baby has hiccups.",
                                         "My baby sounds stuffy or has been sneezing. Is that normal?",
                                         "Will my baby have their vision tested?", "Can I put clothes on my baby?"]},
    "Can I take a shower?": {"note": "Usually yes, but check with your nurse if you have an IV or other restrictions."},
    "Can I put on my own clothes?": {
        "note": "Yes, as long as you feel comfortable and have been cleared by your nurse."},
    "How often should I change my pad?": {
        "note": "Change your pad every 2–4 hours or when it becomes saturated. Let your nurse know if you’re soaking the big pad in less than 1 hour or clots bigger than a golf ball."},
    "How often should I use the breast pump?": {
        "note": "Every 2–3 hours if you're trying to build or maintain supply. Your nurse or lactation consultant can guide you."},
    "I'm not getting any breastmilk when I pump. Is that normal?": {
        "note": "Yes, it’s common early on. It can take a few days for milk to come in. Keep pumping every 2–3 hours and let your nurse know if concerned."},
    "How often should I feed my baby?": {
        "note": "At least every 2–3 hours and on demand. Feeding cues include rooting, sucking hands, and fussiness."},
    "I'm concerned that my baby is not getting enough breastmilk.": {
        "note": "Let your nurse know so they can assist. Signs your baby is feeding well include swallowing sounds and regular wet diapers. The back of the feeding log show how many diapers your baby should have."},
    "My baby has hiccups.": {
        "note": "Hiccups are normal in newborns and usually go away on their own. Try holding your baby upright."},
    "My baby sounds stuffy or has been sneezing. Is that normal?": {
        "note": "Yes — newborns often sneeze and sound congested. If your baby has trouble feeding or breathing, let your nurse know."},
    "Will my baby have their vision tested?": {
        "note": "No, but the pediatrician will look at your baby's eyes with a light."},
    "Can I put clothes on my baby?": {
        "note": "Yes, you may dress your baby, even if they have not had a bath. Skin-to-skin is encouraged, especially in the early days."},

    "I want to know about going home": {
        "question": "What would you like to know?",
        "options": ["Vaginal delivery", "C-section delivery", "Baby", "When will I get my discharge paperwork?",
                    "Do I have to take a wheelchair?"]
    },
    "When will I get my discharge paperwork?": {
        "note": "Once the OB-GYN and the pediatrician has put in their notes and discharge orders, your nurse can print out paperwork."},
    "Do I have to take a wheelchair?": {
        "note": "No, but a staff member has to go with you. If the nursing staff is busy, a transport worker will be the one to escort you out."},
    "Vaginal delivery": {
        "note": "If you delivered vaginally, the minimum stay is 24 hours after delivery. An OB-GYN has to give the ok for discharge and update the computer. Typically, as long as your bleeding, blood pressure, and pain are under control, you should be allowed to discharge. However, the OB-GYN makes the final decision."},
    "C-section delivery": {
        "note": "If you delivered by C-section, the minimum stay is 48 hours. The OB-GYN will give the discharge order if appropriate. Typically, as long as your pain, blood pressure, and bleeding are normal, you will be discharged."},
    "Baby": {
        "note": "The pediatrician needs to assess your baby every day that you're in the hospital. The minimum stay for baby is 24 hours. Your baby needs to be feeding from the breast or bottle well, have an appropriate weight loss, passed the 24-hour tests, hearing test, and be peeing and pooping. If born before 37 weeks or if GBS positive without adequate antibiotics, baby may need to stay 48 hours. Discuss your baby's discharge plan with the nurse and pediatrician."}
}
