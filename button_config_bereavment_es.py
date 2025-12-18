# button_config_bereavement_es.py
button_data = {
    "greeting": "Hola. Estamos aquí para apoyarle.",
    "custom_note_placeholder": "Si no encuentra lo que necesita o requiere más de un artículo, por favor escriba un breve mensaje en el recuadro de abajo.",
    "empty_custom_note": "Por favor, escriba un mensaje en el cuadro.",
    "send_note_button": "Enviar nota",
    "cna_notification": "✅ Se ha notificado al asistente de enfermería.",
    "nurse_notification": "✅ Se ha notificado a la enfermera.",
    "back_text": "⬅ Regresar",
    "unknown_input": "Perdón, no entendí. Por favor use los botones.",

    # --- Main Menu Options (Bereavement) ---
    "main_buttons": [
        "Mi bomba de IV está sonando",
        "Necesito medicamentos",
        "Necesito suministros",
        "Baño / Ducha",
        "Hielo / Agua",
        "Quiero ver a mi bebé",
        "Necesito hablar con el trabajador social",
        "Tengo preguntas",
        "Quiero saber sobre el alta"
    ],

    # --- Acciones directas / Submenús simples ---
    "Tengo una emergencia": {"action": "Notify Nurse"},
    "Mi bomba de IV está sonando": {"action": "Notify Nurse"},

    "Hielo / Agua": {
        "question": "Si tiene una persona de apoyo con usted, puede ir a nuestra sala de nutrición, que tiene agua, hielo picado, jugo y pequeños bocadillos. El personal puede mostrarle dónde se encuentra. ¿Qué le gustaría?",
        "options": [
            "Necesito agua con hielo",
            "Necesito hielo picado",
            "Necesito agua, sin hielo",
            "Necesito agua caliente"
        ]
    },
    "Necesito agua con hielo": {"action": "Notify CNA"},
    "Necesito hielo picado": {"action": "Notify CNA"},
    "Necesito agua, sin hielo": {"action": "Notify CNA"},
    "Necesito agua caliente": {"action": "Notify CNA"},

    "Baño / Ducha": {
        "question": "Si ya ha ido al baño una vez con un miembro del personal y se siente estable, puede usar el baño por su cuenta. Avísenos si todavía necesita ayuda. ¿Qué necesita?",
        "options": [
            "Necesito ayuda para ir al baño",
            "Necesito cubrir mi vía IV para ducharme",
            "¿Puedo tomar una ducha?"
        ]
    },
    "Necesito ayuda para ir al baño": {"action": "Notify CNA"},
    "Necesito cubrir mi vía IV para ducharme": {"action": "Notify CNA"},
    "¿Puedo tomar una ducha?": {"note": "Normalmente sí, pero consulte con su enfermera si tiene una vía intravenosa u otras restricciones."},

    # --- Suministros ---
    "Necesito suministros": {
        "question": "¿Qué necesita?",
        "options": ["Toallas sanitarias", "Ropa interior de malla", "Compresa de hielo", "Almohadas"]
    },
    "Almohadas": {"action": "Notify CNA"},
    "Ropa interior de malla": {"action": "Notify CNA"},
    "Toallas sanitarias": {
        "question": "¿Qué tipo de toalla sanitaria necesita?",
        "options": ["Toallas azules", "Toallas blancas"]
    },
    "Toallas azules": {"action": "Notify CNA"},
    "Toallas blancas": {"action": "Notify CNA"},
    "Compresa de hielo": {
        "question": "¿Dónde necesita la compresa de hielo?",
        "options": ["Compresa de hielo para el perineo", "Compresa de hielo para la incisión de la cesárea", "Compresa de hielo para los senos"]
    },
    "Compresa de hielo para el perineo": {"action": "Notify CNA"},
    "Compresa de hielo para la incisión de la cesárea": {"action": "Notify CNA"},
    "Compresa de hielo para los senos": {"action": "Notify CNA"},

    # --- Medicamentos / Síntomas ---
    "Necesito medicamentos": {
        "question": "¿Cuál es su síntoma principal?",
        "options": ["Dolor", "Náuseas/Vómitos", "Picazón", "Dolor por gases", "Estreñimiento"]
    },
    "Dolor": {"action": "Notify Nurse"},
    "Náuseas/Vómitos": {"action": "Notify Nurse"},
    "Picazón": {"action": "Notify Nurse"},
    "Dolor por gases": {"action": "Notify Nurse"},
    "Estreñimiento": {"action": "Notify Nurse"},

    # --- Bereavement específico ---
    "Quiero ver a mi bebé": {
        "note": "Estamos contactando a su enfermera para ayudarle a ver a su bebé.",
        "options": [],
        "action": "Notify Nurse"
    },
    "Necesito hablar con el trabajador social": {
        "note": "Estamos avisando al trabajador social para brindarle apoyo y recursos.",
        "options": [],
        "action": "Notify Nurse"
    },

    # --- Preguntas ---
    "Tengo preguntas": {
        "note": "Si su pregunta no está en la lista, su enfermera vendrá tan pronto como sea posible.",
        "options": [
            "¿Puedo ponerme mi propia ropa?",
            "¿Cada cuánto debo cambiar mi toalla sanitaria?"
        ]
    },
    "¿Puedo ponerme mi propia ropa?": {"note": "Sí, siempre que se sienta cómoda y su enfermera le haya dado el visto bueno."},
    "¿Cada cuánto debo cambiar mi toalla sanitaria?": {"note": "Cambie su toalla cada 2–4 horas o cuando esté saturada. Avise si empapa una toalla en menos de 1 hora o si hay coágulos grandes."},

    # --- Alta ---
    "Quiero saber sobre el alta": {
        "question": "¿Qué le gustaría saber?",
        "options": ["Parto vaginal", "Parto por cesárea", "¿Cuándo recibiré mis papeles de alta?", "¿Tengo que usar una silla de ruedas?"]
    },
    "Parto vaginal": {"note": "Estancia mínima 24 h tras parto vaginal; el ginecólogo autoriza el alta."},
    "Parto por cesárea": {"note": "Estancia mínima 48 h tras cesárea; el ginecólogo indicará el alta si corresponde."},
    "¿Cuándo recibiré mis papeles de alta?": {"note": "Una vez que el ginecólogo ingrese notas y órdenes de alta, su enfermera imprimirá la documentación."},
    "¿Tengo que usar una silla de ruedas?": {"note": "No es obligatorio, pero alguien del personal debe acompañarle. Si enfermería está ocupada, le llevará personal de traslado."}
}


