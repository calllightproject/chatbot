# button_config_es.py
button_data = {
    "greeting": "¡Hola! ¿Cómo puedo ayudarle?",
    "cna_notification": "✅ Se ha notificado al asistente de enfermería.",
    "nurse_notification": "✅ Se ha notificado a la enfermera.",
    "main_buttons": [
        "Tengo una emergencia",
        "Necesito suministros",
        "Necesito medicamentos",
        "Tengo preguntas",
        "Quiero saber sobre el alta",
        "Necesito ayuda para ir al baño",
        "Necesito cubrir mi vía IV para bañarme",
        "Necesito ayuda para amamantar",
        "Azúcar en la sangre"
    ],

    "Tengo una emergencia": {"action": "Notify Nurse"},
    "Necesito ayuda para ir al baño": {"action": "Notify CNA"},
    "Necesito cubrir mi vía IV para bañarme": {"action": "Notify CNA"},
    "Necesito ayuda para amamantar": {
        "action": "Notify Nurse",
        "note": "✅ Se ha notificado a su enfermera. Mientras tanto, puede prepararse asegurándose de que su bebé tenga un pañal limpio y esté desvestido para el contacto piel con piel."
    },

    "Azúcar en la sangre": {
        "question": "¿Es para la mamá o para el/la bebé?",
        "options": ["Mamá", "Bebé (azúcar en la sangre)"]
    },
    "Mamá": {"action": "Notify CNA"},
    "Bebé (azúcar en la sangre)": {"action": "Notify Nurse"},

    "Necesito suministros": {
        "question": "¿Para el/la bebé o para la mamá?",
        "options": ["Artículos para bebé", "Artículos para mamá"]
    },

    "Artículos para bebé": {
        "question": "¿Qué necesita su bebé?",
        "options": ["Pañales", "Fórmula", "Manta para envolver", "Toallitas húmedas"]
    },
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
    "Similac Total Comfort (etiqueta morada)": {"action": "Notify CNA"},
    "Similac 360 (etiqueta azul)": {"action": "Notify CNA"},
    "Similac Neosure (etiqueta amarilla)": {"action": "Notify CNA"},
    "Enfamil Newborn (etiqueta amarilla)": {"action": "Notify CNA"},
    "Enfamil Gentlease (etiqueta morada)": {"action": "Notify CNA"},

    "Artículos para mamá": {
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

    "Pañales": {"action": "Notify CNA"},
    "Manta para envolver": {"action": "Notify CNA"},
    "Toallitas húmedas": {"action": "Notify CNA"},
    "Ropa interior de malla": {"action": "Notify CNA"},

    "Necesito medicamentos": {
        "question": "¿Cuál es su síntoma principal?",
        "options": ["Dolor", "Náuseas/Vómitos", "Picazón", "Dolor por gases", "Estreñimiento"]
    },
    "Dolor": {"action": "Notify Nurse"},
    "Náuseas/Vómitos": {"action": "Notify Nurse"},
    "Picazón": {"action": "Notify Nurse"},
    "Dolor por gases": {"action": "Notify Nurse"},
    "Estreñimiento": {"action": "Notify Nurse"},

    "Tengo preguntas": {
        "question": "¿Preguntas sobre la mamá o el bebé?",
        "options": ["Preguntas sobre la mamá", "Preguntas sobre el bebé"]
    },

    "Preguntas sobre la mamá": {
        "note": "Si su pregunta no está en la lista, su enfermera vendrá tan pronto como sea posible.",
        "options": [
            "¿Puedo tomar una ducha?",
            "¿Puedo ponerme mi propia ropa?",
            "¿Cómo de seguido debo cambiar mi toalla sanitaria?",
            "¿Cómo de seguido debo usar el sacaleches?",
            "No consigo sacar leche cuando uso el sacaleches. ¿Es normal?"
        ]
    },
    "Preguntas sobre el/la bebé": {
        "note": "Si su pregunta no está en la lista, su enfermera vendrá tan pronto como sea posible.",
        "options": [
            "¿Cómo de seguido debo alimentar a mi bebé?",
            "Me preocupa que mi bebé no esté recibiendo suficiente leche materna.",
            "Mi bebé tiene hipo.",
            "Mi bebé suena congestionado o ha estado estornudando. ¿Es normal?",
            "¿Le harán a mi bebé un examen de la vista?",
            "¿Puedo vestir a mi bebé con su propia ropa?"
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
    "¿Cómo de seguido debo usar el sacaleches?": {
        "note": "Cada 2-3 horas si está tratando de establecer o mantener la producción de leche. Su enfermera o asesora de lactancia pueden guiarla."
    },
    "No consigo sacar leche cuando uso el sacaleches. ¿Es normal?": {
        "note": "Sí, es común al principio. La leche puede tardar unos días en bajar. Siga usando el sacaleches cada 2-3 horas e informe a su enfermera si está preocupada."
    },
    "¿Cómo de seguido debo alimentar a mi bebé?": {
        "note": "Al menos cada 2-3 horas y cuando lo pida. Las señales de hambre incluyen buscar el pecho, chuparse las manos y estar inquieto."
    },
    "Me preocupa que mi bebé no esté recibiendo suficiente leche materna.": {
        "note": "Informe a su enfermera para que pueda ayudar. Las señales de que su bebé se está alimentando bien incluyen sonidos de deglución y pañales mojados regularmente. El reverso del registro de alimentación muestra cuántos pañales debe tener su bebé."
    },
    "Mi bebé tiene hipo.": {
        "note": "El hipo es normal en los recién nacidos y generalmente desaparece por sí solo. Intente sostener a su bebé en posición vertical."
    },
    "Mi bebé suena congestionado o ha estado estornudando. ¿Es normal?": {
        "note": "Sí, los recién nacidos a menudo estornudan y suenan congestionados. Si su bebé tiene problemas para alimentarse o respirar, informe a su enfermera."
    },
    "¿Le harán a mi bebé un examen de la vista?": {
        "note": "No, pero el pediatra mirará los ojos de su bebé con una luz."
    },
    "¿Puedo vestir a mi bebé con su propia ropa?": {
        "note": "Sí, puede vestir a su bebé, incluso si no se ha bañado. Se recomienda el contacto piel con piel, especialmente en los primeros días."
    },

    "Quiero saber sobre el alta": {
        "question": "¿Qué le gustaría saber?",
        "options": ["Parto vaginal", "Parto por cesárea", "Bebé", "¿Cuándo recibiré mis papeles de alta?", "¿Tengo que usar una silla de ruedas?"]
    },
    "¿Cuándo recibiré mis papeles de alta?": {
        "note": "Una vez que el ginecólogo y el pediatra hayan ingresado sus notas y órdenes de alta, su enfermera podrá imprimir la documentación."
    },
    "¿Tengo que usar una silla de ruedas?": {
        "note": "No, pero un miembro del personal tiene que acompañarla. Si el personal de enfermería está ocupado, un transportista la acompañará a la salida."
    },
    "Parto vaginal": {
        "note": "Si tuvo un parto vaginal, la estadía mínima es de 24 horas después del parto. Un ginecólogo debe dar el visto bueno para el alta y actualizar el sistema. Típicamente, siempre que su sangrado, presión arterial y dolor estén bajo control, se le permitirá el alta. Sin embargo, el ginecólogo toma la decisión final."
    },
    "Parto por cesárea": {
        "note": "Si tuvo un parto por cesárea, la estadía mínima es de 48 horas. El ginecólogo dará la orden de alta si es apropiado. Típicamente, siempre que su dolor, presión arterial y sangrado sean normales, será dada de alta."
    },
    "Bebé": {
        "note": "El pediatra necesita evaluar a su bebé todos los días que esté en el hospital. La estadía mínima para el bebé es de 24 horas. Su bebé necesita alimentarse bien del pecho o del biberón, tener una pérdida de peso adecuada, pasar las pruebas de 24 horas, la prueba de audición, y estar orinando y defecando. Si nació antes de las 37 semanas o si fue positivo para GBS sin los antibióticos adecuados, es posible que el bebé deba quedarse 48 horas. Discuta el plan de alta de su bebé con la enfermera y el pediatra."
    }
}
