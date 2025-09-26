# button_config_bereavement_es.py
button_data = {
    "greeting": "Hola. Estamos aquí para apoyarle.",
    "custom_note_placeholder": "Escriba su nota para la enfermera aquí...",
    "empty_custom_note": "Por favor, escriba un mensaje en el cuadro.",
    "send_note_button": "Enviar nota",
    "cna_notification": "✅ Se ha notificado al asistente de enfermería.",
    "nurse_notification": "✅ Se ha notificado a la enfermera.",
    "back_text": "⬅ Regresar",
    "unknown_input": "Perdón, no entendí. Por favor use los botones.",

  # --- Main Menu Options (Bereavement) ---
"main_buttons": [
    "Tengo una emergencia",
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



    "Tengo una emergencia": {"action": "Notificar a la enfermera"},
    "Mi bomba de IV está sonando": {"action": "Notificar a la enfermera"},

    "Hielo / Agua": {
        "question": "Si tiene una persona de apoyo con usted, puede ir a nuestra sala de nutrición, que tiene agua, hielo picado, jugo y pequeños bocadillos. El personal puede mostrarle dónde se encuentra. ¿Qué le gustaría?",
        "options": [
            "Necesito agua con hielo",
            "Necesito hielo picado",
            "Necesito agua, sin hielo",
            "Necesito agua caliente"
        ]
    },
    "Necesito agua con hielo": {"action": "Notificar al asistente de enfermería"},
    "Necesito hielo picado": {"action": "Notificar al asistente de enfermería"},
    "Necesito agua, sin hielo": {"action": "Notificar al asistente de enfermería"},
    "Necesito agua caliente": {"action": "Notificar al asistente de enfermería"},

    "Baño / Ducha": {
        "question": "Si ya ha ido al baño una vez con un miembro del personal y se siente estable, puede usar el baño por su cuenta. Avísenos si todavía necesita ayuda. ¿Qué necesita?",
        "options": [
            "Necesito ayuda para ir al baño",
            "Necesito cubrir mi vía IV para ducharme",
            "¿Puedo tomar una ducha?"
        ]
    },
    "Necesito ayuda para ir al baño": {"action": "Notificar al asistente de enfermería"},
    "Necesito cubrir mi vía IV para ducharme": {"action": "Notificar al asistente de enfermería"},
    "¿Puedo tomar una ducha?": {"note": "Normalmente sí, pero consulte con su enfermera si tiene una vía intravenosa u otras restricciones."},

    "Necesito suministros": {
        "question": "¿Qué necesita?",
        "options": ["Toallas sanitarias", "Ropa interior de malla", "Compresa de hielo", "Almohadas"]
    },
    "Almohadas": {"action": "Notificar al asistente de enfermería"},
    "Ropa interior de malla": {"action": "Notificar al asistente de enfermería"},
    "Toallas sanitarias": {
        "question": "¿Qué tipo de toalla sanitaria necesita?",
        "options": ["Toallas azules", "Toallas blancas"]
    },
    "Toallas azules": {"action": "Notificar al asistente de enfermería"},
    "Toallas blancas": {"action": "Notificar al asistente de enfermería"},
    "Compresa de hielo": {
        "question": "¿Dónde necesita la compresa de hielo?",
        "options": ["Compresa de hielo para el perineo", "Compresa de hielo para la incisión de la cesárea", "Compresa de hielo para los senos"]
    },
    "Compresa de hielo para el perineo": {"action": "Notificar al asistente de enfermería"},
    "Compresa de hielo para la incisión de la cesárea": {"action": "Notificar al asistente de enfermería"},
    "Compresa de hielo para los senos": {"action": "Notificar al asistente de enfermería"},

    "Necesito medicamentos": {
        "question": "¿Cuál es su síntoma principal?",
        "options": ["Dolor", "Náuseas/Vómitos", "Picazón", "Dolor por gases", "Estreñimiento"]
    },
    "Dolor": {"action": "Notificar a la enfermera"},
    "Náuseas/Vómitos": {"action": "Notificar a la enfermera"},
    "Picazón": {"action": "Notificar a la enfermera"},
    "Dolor por gases": {"action": "Notificar a la enfermera"},
    "Estreñimiento": {"action": "Notificar a la enfermera"},

    "Tengo preguntas": {
        "note": "Si su pregunta no está en la lista, su enfermera vendrá tan pronto como sea posible.",
        "options": [
            "¿Puedo ponerme mi propia ropa?",
            "¿Cada cuánto debo cambiar mi toalla sanitaria?"
        ]
    },
    "¿Puedo ponerme mi propia ropa?": {"note": "Sí, siempre que se sienta cómoda y su enfermera le haya dado el visto bueno."},
    "¿Cada cuánto debo cambiar mi toalla sanitaria?": {"note": "Cambie su toalla cada 2–4 horas o cuando esté saturada. Avise si empapa una toalla en menos de 1 hora o si hay coágulos grandes."},

    "Quiero saber sobre el alta": {
        "question": "¿Qué le gustaría saber?",
        "options": ["Parto vaginal", "Parto por cesárea", "¿Cuándo recibiré mis papeles de alta?", "¿Tengo que usar una silla de ruedas?"]
    },
    "¿Cuándo recibiré mis papeles de alta?": {"note": "Una vez que el ginecólogo ingrese notas y órdenes de alta, su enfermera imprimirá la documentación."},
    "¿Tengo que usar una silla de ruedas?": {"note": "No es obligatorio, pero alguien del personal debe acompañarle. Si enfermería está ocupada, le llevará personal de traslado."},
    "Parto vaginal": {"note": "Estancia mínima 24 h tras parto vaginal; el ginecólogo autoriza el alta."},
    "Parto por cesárea": {"note": "Estancia mínima 48 h tras cesárea; el ginecólogo indicará el alta si corresponde."}
}


