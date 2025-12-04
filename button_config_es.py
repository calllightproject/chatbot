# button_config_es.py
button_data = {
    # --- Core Notifications & Text ---
    "greeting": "¡Hola! ¿Cómo puedo ayudarle?",
    "custom_note_placeholder": "Si no encuentra lo que necesita o requiere más de un artículo, por favor escriba un breve mensaje en el recuadro de abajo.",
    "empty_custom_note": "Por favor, escriba un mensaje en el cuadro.",
    "send_note_button": "Enviar nota",
    "back_text": "⬅ Regresar",
    "cna_notification": "✅ Se ha notificado al asistente de enfermería.",
    "nurse_notification": "✅ Se ha notificado a la enfermera.",
    "demographic_question": "¿Es este su primer bebé?",
    "demographic_yes": "Sí",
    "demographic_no": "No",
    "ai_follow_up_question": "¿Le gustaría hablar con su enfermera?",
    "ai_yes": "Sí, hablar con la enfermera",
    "ai_no": "No, estoy bien",
    "unknown_input": "Perdón, no entendí. Por favor use los botones.",

   # --- Main Menu Options ---
"main_buttons": [
    "Tengo una emergencia",
    "Mi bomba de IV está sonando",
    "Necesito medicamentos",
    "Necesito suministros",
    "Baño / Ducha",
    "Hielo / Agua",
    "Azúcar en la sangre",
    "Necesito ayuda para amamantar",
    "Tengo preguntas",
    "Quiero saber sobre el alta"
],


    # --- Direct Actions & Simple Sub-menus ---
    "Tengo una emergencia": {"action": "Notificar a la enfermera"},
    "Mi bomba de IV está sonando": {"action": "Notificar a la enfermera"},

    "Necesito ayuda para amamantar": {
        "action": "Notificar a la enfermera",
        "note": "✅ Se ha notificado a su enfermera. Mientras tanto, puede prepararse asegurándose de que su bebé tenga un pañal limpio y esté desvestido para el contacto piel con piel."
    },

    "Azúcar en la sangre": {
        "question": "¿Es para la mamá o para el/la bebé?",
        "options": ["Mamá (azúcar en la sangre)", "Bebé (azúcar en la sangre)"]
    },
    "Mamá (azúcar en la sangre)": {"action": "Notificar al asistente de enfermería"},
    "Bebé (azúcar en la sangre)": {"action": "Notificar a la enfermera"},

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
        "question": "Si ya ha ido al baño una vez con un miembro del personal y se siente estable, puede usar el baño por su cuenta. Por favor, avísenos si todavía necesita ayuda. ¿Qué necesita?",
        "options": [
            "Necesito ayuda para ir al baño",
            "Necesito cubrir mi vía IV para bañarme",
            "¿Puedo tomar una ducha?"
        ]
    },
    "Necesito ayuda para ir al baño": {"action": "Notificar al asistente de enfermería"},
    "Necesito cubrir mi vía IV para bañarme": {"action": "Notificar al asistente de enfermería"},
    "¿Puedo tomar una ducha?": {
        "note": "Normalmente sí, pero consulte con su enfermera si tiene una vía intravenosa u otras restricciones.",
        "follow_up": True
    },

    # --- Supplies Category ---
    "Necesito suministros": {
        "question": "¿Para el/la bebé o para la mamá?",
        "options": ["Artículos para bebé", "Artículos para mamá"]
    },
    "Artículos para bebé": {
        "question": "¿Qué necesita su bebé?",
        "options": ["Pañales", "Fórmula", "Manta para envolver", "Toallitas húmedas"]
    },
    "Artículos para mamá": {
        "question": "¿Qué necesita?",
        "options": ["Toallas sanitarias", "Ropa interior de malla", "Compresa de hielo", "Almohadas"]
    },
    "Almohadas": {"action": "Notificar al asistente de enfermería"},
    "Pañales": {"action": "Notificar al asistente de enfermería"},
    "Manta para envolver": {"action": "Notificar al asistente de enfermería"},
    "Toallitas húmedas": {"action": "Notificar al asistente de enfermería"},

    "Fórmula": {
        "question": "¿Qué fórmula necesita?",
        "options": [
            "Similac Total Comfort (etiqueta morada)",
            "Similac 360 (etiqueta azul)",
            "Similac Neosure (etiqueta amarilla)",
            "Enfamil Newborn (etiqueta amarilla)",
            "Enfamil Gentlease (etiqueta morada)"
        ]
    },
    "Similac Total Comfort (etiqueta morada)": {"action": "Notificar al asistente de enfermería"},
    "Similac 360 (etiqueta azul)": {"action": "Notificar al asistente de enfermería"},
    "Similac Neosure (etiqueta amarilla)": {"action": "Notificar al asistente de enfermería"},
    "Enfamil Newborn (etiqueta amarilla)": {"action": "Notificar al asistente de enfermería"},
    "Enfamil Gentlease (etiqueta morada)": {"action": "Notificar al asistente de enfermería"},

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

    # --- Medication Category ---
    "Necesito medicamentos": {
        "question": "¿Cuál es su síntoma principal?",
        "options": ["Dolor", "Náuseas/Vómitos", "Picazón", "Dolor por gases", "Estreñimiento"]
    },
    "Dolor": {"action": "Notificar a la enfermera"},
    "Náuseas/Vómitos": {"action": "Notificar a la enfermera"},
    "Picazón": {"action": "Notificar a la enfermera"},
    "Dolor por gases": {"action": "Notificar a la enfermera"},
    "Estreñimiento": {"action": "Notificar a la enfermera"},

    # --- Questions Category ---
    "Tengo preguntas": {
        "question": "¿Preguntas sobre la mamá o el bebé?",
        "options": ["Preguntas sobre la mamá", "Preguntas sobre el bebé"]
    },
    "Preguntas sobre la mamá": {
        "note": "Si su pregunta no está en la lista, su enfermera vendrá tan pronto como sea posible.",
        "options": [
            "¿Puedo ponerme mi propia ropa?",
            "¿Cada cuánto debo cambiar mi toalla sanitaria?",
            "¿Cada cuánto debo usar el sacaleches?",
            "No consigo sacar leche cuando uso el sacaleches. ¿Es normal?"
        ]
    },
    "Preguntas sobre el bebé": {
        "note": "Si su pregunta no está en la lista, su enfermera vendrá tan pronto como sea posible.",
        "options": [
            "¿Cada cuánto debo alimentar a mi bebé?",
            "Me preocupa que mi bebé no esté recibiendo suficiente leche materna.",
            "Mi bebé tiene hipo.",
            "Mi bebé suena congestionado o ha estado estornudando. ¿Es normal?",
            "¿Le harán a mi bebé un examen de la vista?",
            "¿Puedo vestir a mi bebé con su propia ropa?"
        ]
    },
    "¿Puedo ponerme mi propia ropa?": {"note": "Sí, siempre que se sienta cómoda y su enfermera le haya dado el visto bueno."},
    "¿Cada cuánto debo cambiar mi toalla sanitaria?": {"note": "Cambie su toalla cada 2–4 horas o cuando esté saturada. Avise a su enfermera si empapa una toalla en menos de 1 hora o si tiene coágulos más grandes que una pelota de golf."},
    "¿Cada cuánto debo usar el sacaleches?": {"note": "Cada 2–3 horas si desea establecer o mantener la producción. Su enfermera o asesora de lactancia puede guiarla."},
    "No consigo sacar leche cuando uso el sacaleches. ¿Es normal?": {"note": "Sí, es común al principio. Puede tardar unos días en bajar la leche. Continúe cada 2–3 horas y avise si tiene dudas."},
    "¿Cada cuánto debo alimentar a mi bebé?": {"note": "Al menos cada 2–3 horas y a demanda. Señales: buscar el pecho, chuparse las manos, inquietud."},
    "Me preocupa que mi bebé no esté recibiendo suficiente leche materna.": {"note": "Avise a su enfermera. Señales de buena alimentación: sonidos de deglución y pañales mojados regulares."},
    "Mi bebé tiene hipo.": {"note": "El hipo es normal y suele desaparecer solo. Sostenga a su bebé en posición erguida."},
    "Mi bebé suena congestionado o ha estado estornudando. ¿Es normal?": {"note": "Sí, es común en recién nacidos. Si hay dificultad para alimentarse o respirar, avise a su enfermera."},
    "¿Le harán a mi bebé un examen de la vista?": {"note": "No, pero el pediatra revisará los ojos con una luz."},
    "¿Puedo vestir a mi bebé con su propia ropa?": {"note": "Sí, incluso si aún no se ha bañado. Se fomenta el contacto piel con piel, especialmente al inicio."},

    # --- Going Home Category ---
    "Quiero saber sobre el alta": {
        "question": "¿Qué le gustaría saber?",
        "options": ["Parto vaginal", "Parto por cesárea", "Bebé", "¿Cuándo recibiré mis papeles de alta?", "¿Tengo que usar una silla de ruedas?"]
    },
    "Parto vaginal": {"note": "Si fue parto vaginal, la estancia mínima es de 24 horas. El ginecólogo debe autorizar el alta. Si el sangrado, la presión y el dolor están controlados, normalmente podrá irse; la decisión final es del ginecólogo."},
    "Parto por cesárea": {"note": "Si fue cesárea, estancia mínima de 48 horas. Si el dolor, la presión y el sangrado están normales, probablemente será dada de alta cuando el ginecólogo lo indique."},
    "Bebé": {"note": "El pediatra evalúa al bebé diariamente. Estancia mínima 24 h. Debe alimentarse bien, tener pérdida de peso adecuada, pasar pruebas de 24 h, prueba de audición y orinar/defecar. Si <37 semanas o GBS sin antibióticos adecuados, quizá 48 h."},
    "¿Cuándo recibiré mis papeles de alta?": {"note": "Una vez que el ginecólogo y el pediatra ingresen notas y órdenes de alta, su enfermera imprimirá la documentación."},
    "¿Tengo que usar una silla de ruedas?": {"note": "No es obligatorio, pero alguien del personal debe acompañarle. Si enfermería está ocupada, le llevará personal de traslado."}
}


