# button_config_bereavement_es.py
button_data = {
    # --- Core Notifications & Text ---
    "greeting": "Hola. Estamos aquí para apoyarle.",
    "cna_notification": "✅ Se ha notificado al asistente de enfermería.",
    "nurse_notification": "✅ Se ha notificado a la enfermera.",
    "back_text": "⬅ Regresar",

    # --- Main Menu Options ---
    "main_buttons": [
        "Tengo una emergencia",
        "Necesito suministros",
        "Necesito medicamentos",
        "Tengo preguntas",
        "Quiero saber sobre el alta",
        "Necesito ayuda para ir al baño",
        "Necesito cubrir mi vía IV para ducharme",
        "Control de azúcar en la sangre para mí"
    ],

    # --- Direct Actions & Simple Sub-menus ---
    "Tengo una emergencia": {"action": "Notify Nurse"},
    "Necesito ayuda para ir al baño": {"action": "Notify CNA"},
    "Necesito cubrir mi vía IV para ducharme": {"action": "Notify CNA"},
    "Control de azúcar en la sangre para mí": {"action": "Notify CNA"},

    # --- Supplies Category ---
    "Necesito suministros": {
        "question": "¿Qué necesita?",
        "options": ["Toallas sanitarias", "Ropa interior de malla", "Compresa de hielo"]
    },
    "Toallas sanitarias": {
        "question": "¿Qué tipo de toalla sanitaria necesita?",
        "options": ["Toallas azules", "Toallas blancas"]
    },
    "Toallas azules": {"action": "Notify CNA"},
    "Toallas blancas": {"action": "Notify CNA"},
    "Compresa de hielo": {
        "question": "¿Dónde necesita la compresa de hielo?",
        "options": ["Para el perineo", "Para la incisión de la cesárea", "Para los senos"]
    },
    "Para el perineo": {"action": "Notify CNA"},
    "Para la incisión de la cesárea": {"action": "Notify CNA"},
    "Para los senos": {"action": "Notify CNA"},
    "Ropa interior de malla": {"action": "Notify CNA"},

    # --- Medication Category ---
    "Necesito medicamentos": {
        "question": "¿Cuál es su síntoma principal?",
        "options": ["Dolor", "Náuseas/Vómitos", "Picazón", "Dolor por gases", "Estreñimiento"]
    },
    "Dolor": {"action": "Notify Nurse"},
    "Náuseas/Vómitos": {"action": "Notify Nurse"},
    "Picazón": {"action": "Notify Nurse"},
    "Dolor por gases": {"action": "Notify Nurse"},
    "Estreñimiento": {"action": "Notify Nurse"},

    # --- Questions Category ---
    "Tengo preguntas": {
        "note": "Si su pregunta no está en la lista, su enfermera vendrá tan pronto como sea posible.",
        "options": [
            "¿Puedo tomar una ducha?",
            "¿Puedo ponerme mi propia ropa?",
            "¿Cómo de seguido debo cambiar mi toalla sanitaria?",
        ]
    },
    "¿Puedo tomar una ducha?": {
        "note": "Normalmente sí, pero consulte con su enfermera si tiene una vía intravenosa u otras restricciones."
    },
    "¿Puedo ponerme mi propia ropa?": {
        "note": "Sí, siempre y cuando se sienta cómoda y su enfermera le haya dado el visto bueno."
    },
    "¿Cómo de seguido debo cambiar mi toalla sanitaria?": {
        "note": "Cambie su toalla cada 2-4 horas o cuando esté saturada. Informe a su enfermera si está empapando una toalla grande en menos de 1 hora o si tiene coágulos más grandes que una pelota de golf."
    },

    # --- Going Home Category ---
    "Quiero saber sobre el alta": {
        "question": "¿Qué le gustaría saber?",
        "options": ["Parto vaginal", "Parto por cesárea", "¿Cuándo recibiré mis papeles de alta?",
                    "¿Tengo que usar una silla de ruedas?"]
    },
    "¿Cuándo recibiré mis papeles de alta?": {
        "note": "Una vez que el ginecólogo haya ingresado sus notas y órdenes de alta, su enfermera podrá imprimir la documentación."
    },
    "¿Tengo que usar una silla de ruedas?": {
        "note": "No, pero un miembro del personal tiene que acompañarla. Si el personal de enfermería está ocupado, un transportista la acompañará a la salida."
    },
    "Parto vaginal": {
        "note": "Si tuvo un parto vaginal, la estadía mínima es de 24 horas después del parto. Un ginecólogo debe dar el visto bueno para el alta y actualizar el sistema. Típicamente, siempre que su sangrado, presión arterial y dolor estén bajo control, se le permitirá el alta. Sin embargo, el ginecólogo toma la decisión final."
    },
    "Parto por cesárea": {
        "note": "Si tuvo un parto por cesárea, la estadía mínima es de 48 horas. El ginecólogo dará la orden de alta si es apropiado. Típicamente, siempre que su dolor, presión arterial y sangrado sean normales, será dada de alta."
    }
}
