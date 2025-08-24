# These two lines MUST be the very first lines in the file.
import eventlet
eventlet.monkey_patch()

import os
import json
import smtplib
import importlib
from datetime import datetime, date, timezone
from collections import defaultdict
from email.message import EmailMessage

from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, join_room
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*", manage_session=False, ping_timeout=20, ping_interval=10)

# --- Master Data Lists ---
INITIAL_STAFF = {
    'Jackie': 'nurse', 'Carol': 'nurse', 'John': 'nurse',
    'Maria': 'nurse', 'David': 'nurse', 'Susan': 'nurse',
    'Peter': 'cna', 'Linda': 'cna'
}
ALL_ROOMS = [str(room) for room in range(231, 261)]

# --- Lightweight in-app translation (labels only) ---
SPANISH_TO_EN = {
    # Main
    "Tengo una emergencia":"I'm having an emergency",
    "Necesito suministros":"I need supplies",
    "Necesito medicamentos":"I need medication",
    "Mi bomba de IV está sonando":"My IV pump is beeping",
    "Tengo preguntas":"I have questions",
    "Quiero saber sobre el alta":"I want to know about going home",
    "Baño / Ducha":"Bathroom/Shower",
    "Necesito ayuda para amamantar":"I need help breastfeeding",
    "Azúcar en la sangre":"Blood sugar",
    "Hielo / Agua":"Ice Chips/Water",

    # Blood sugar
    "Mamá (azúcar en la sangre)":"Mom (blood sugar)",
    "Bebé (azúcar en la sangre)":"Baby (blood sugar)",
    "Control de azúcar en la sangre para mí":"Blood sugar for me",

    # Water / Ice
    "Necesito agua con hielo":"I need ice water",
    "Necesito hielo picado":"I need ice chips",
    "Necesito agua, sin hielo":"I need water, no ice",
    "Necesito agua caliente":"I need hot water",

    # Bathroom/Shower
    "Necesito ayuda para ir al baño":"I need help to the bathroom",
    "Necesito cubrir mi vía IV para bañarme":"I need my IV covered to shower",
    "Necesito cubrir mi vía IV para ducharme":"I need my IV covered to shower",
    "¿Puedo tomar una ducha?":"Can I take a shower?",

    # Supplies
    "Necesito suministros":"I need supplies",
    "Artículos para bebé":"Baby items",
    "Artículos para mamá":"Mom items",
    "Pañales":"Diapers",
    "Fórmula":"Formula",
    "Manta para envolver":"Swaddle",
    "Toallitas húmedas":"Wipes",
    "Ropa interior de malla":"Mesh underwear",
    "Toallas sanitarias":"Pads",
    "Almohadas":"Pillows",
    "Toallas azules":"Blue pads",
    "Toallas blancas":"White pads",
    "Compresa de hielo":"Ice pack",
    "Compresa de hielo para el perineo":"Ice Pack for Bottom",
    "Compresa de hielo para la incisión de la cesárea":"Ice Pack for C-section incision",
    "Compresa de hielo para los senos":"Ice Pack for Breasts",
    "Similac Total Comfort (etiqueta morada)":"Similac Total Comfort (purple label)",
    "Similac 360 (etiqueta azul)":"Similac 360 (blue label)",
    "Similac Neosure (etiqueta amarilla)":"Similac Neosure (yellow label)",
    "Enfamil Newborn (etiqueta amarilla)":"Enfamil Newborn (yellow label)",
    "Enfamil Gentlease (etiqueta morada)":"Enfamil Gentlease (purple label)",

    # Medication
    "Dolor":"Pain",
    "Náuseas/Vómitos":"Nausea/Vomiting",
    "Picazón":"Itchy",
    "Dolor por gases":"Gas pain",
    "Estreñimiento":"Constipation",

    # Questions
    "Preguntas sobre la mamá":"Questions about mom",
    "Preguntas sobre el bebé":"Questions about baby",
    "¿Puedo ponerme mi propia ropa?":"Can I put on my own clothes?",
    "¿Cómo de seguido debo cambiar mi toalla sanitaria?":"How often should I change my pad?",
    "¿Cómo de seguido debo usar el sacaleches?":"How often should I use the breast pump?",
    "No consigo sacar leche cuando uso el sacaleches. ¿Es normal?":"I'm not getting any breastmilk when I pump. Is that normal?",
    "¿Cómo de seguido debo alimentar a mi bebé?":"How often should I feed my baby?",
    "Me preocupa que mi bebé no esté recibiendo suficiente leche materna.":"I'm concerned that my baby is not getting enough breastmilk.",
    "Mi bebé tiene hipo.":"My baby has hiccups.",
    "Mi bebé suena congestionado o ha estado estornudando. ¿Es normal?":"My baby sounds stuffy or has been sneezing. Is that normal?",
    "¿Le harán a mi bebé un examen de la vista?":"Will my baby have their vision tested?",
    "¿Puedo vestir a mi bebé con su propia ropa?":"Can I put clothes on my baby?",

    # Going home
    "Parto vaginal":"Vaginal delivery",
    "Parto por cesárea":"C-section delivery",
    "Bebé":"Baby",
    "¿Cuándo recibiré mis papeles de alta?":"When will I get my discharge paperwork?",
    "¿Tengo que usar una silla de ruedas?":"Do I have to take a wheelchair?"
}

CHINESE_TO_EN = {
    # Main
    "我有紧急情况":"I'm having an emergency",
    "我需要用品":"I need supplies",
    "我需要药物":"I need medication",
    "我的静脉输液泵在响":"My IV pump is beeping",
    "我有问题":"I have questions",
    "我想了解出院信息":"I want to know about going home",
    "浴室/淋浴":"Bathroom/Shower",
    "我需要母乳喂养方面的帮助":"I need help breastfeeding",
    "血糖":"Blood sugar",
    "冰块/水":"Ice Chips/Water",

    # Blood sugar
    "妈妈（血糖）":"Mom (blood sugar)",
    "宝宝（血糖）":"Baby (blood sugar)",

    # Water / Ice
    "我需要冰水":"I need ice water",
    "我需要冰块":"I need ice chips",
    "我需要不加冰的水":"I need water, no ice",
    "我需要热水":"I need hot water",

    # Bathroom/Shower
    "我需要帮助去卫生间":"I need help to the bathroom",
    "我需要包裹我的静脉输液管以便洗澡":"I need my IV covered to shower",
    "我可以洗澡吗？":"Can I take a shower?",

    # Supplies
    "宝宝用品":"Baby items",
    "妈妈用品":"Mom items",
    "尿布":"Diapers",
    "配方奶":"Formula",
    "襁褓巾":"Swaddle",
    "湿巾":"Wipes",
    "网眼内裤":"Mesh underwear",
    "卫生巾":"Pads",
    "枕头":"Pillows",
    "蓝色卫生巾":"Blue pads",
    "白色卫生巾":"White pads",
    "冰袋":"Ice pack",
    "用于会阴部的冰袋":"Ice Pack for Bottom",
    "用于剖腹产切口的冰袋":"Ice Pack for C-section incision",
    "用于乳房的冰袋":"Ice Pack for Breasts",
    "Similac Total Comfort (紫色标签)":"Similac Total Comfort (purple label)",
    "Similac 360 (蓝色标签)":"Similac 360 (blue label)",
    "Similac Neosure (黄色标签)":"Similac Neosure (yellow label)",
    "Enfamil Newborn (黄色标签)":"Enfamil Newborn (yellow label)",
    "Enfamil Gentlease (紫色标签)":"Enfamil Gentlease (purple label)",

    # Medication
    "疼痛":"Pain",
    "恶心/呕吐":"Nausea/Vomiting",
    "瘙痒":"Itchy",
    "胀气痛":"Gas pain",
    "便秘":"Constipation",

    # Questions
    "关于妈妈的问题":"Questions about mom",
    "关于宝宝的问题":"Questions about baby",
    "我可以穿自己的衣服吗？":"Can I put on my own clothes?",
    "我应该多久更换一次卫生巾？":"How often should I change my pad?",
    "我应该多久使用一次吸奶器？":"How often should I use the breast pump?",
    "我用吸奶器时吸不出母乳，这正常吗？":"I'm not getting any breastmilk when I pump. Is that normal?",
    "我应该多久喂一次宝宝？":"How often should I feed my baby?",
    "我担心宝宝没有吃到足够的母乳。":"I'm concerned that my baby is not getting enough breastmilk.",
    "我的宝宝打嗝了。":"My baby has hiccups.",
    "我的宝宝听起来鼻塞或一直在打喷嚏，这正常吗？":"My baby sounds stuffy or has been sneezing. Is that normal?",
    "会给我的宝宝做视力测试吗？":"Will my baby have their vision tested?",
    "我可以给宝宝穿衣服吗？":"Can I put clothes on my baby?",

    # Going home
    "顺产出院":"Vaginal delivery",
    "剖腹产出院":"C-section delivery",
    "宝宝出院":"Baby",
    "我什么时候能拿到出院文件？":"When will I get my discharge paperwork?",
    "我必须坐轮椅吗？":"Do I have to take a wheelchair?"
}

def translate_to_en(lang: str, text: str) -> str:
    if not text:
        return text
    if lang == 'es':
        return SPANISH_TO_EN.get(text, text)
    if lang.startswith('zh'):
        return CHINESE_TO_EN.get(text, text)
    return text

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("WARNING: DATABASE_URL environment variable not found. Using a local SQLite database.")
    DATABASE_URL = "sqlite:///local_call_light.db"

engine = create_engine(DATABASE_URL, pool_recycle=280, pool_pre_ping=True)

# --- Database Setup ---
def setup_database():
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS requests (
                        id SERIAL PRIMARY KEY,
                        request_id VARCHAR(255) UNIQUE,
                        timestamp TIMESTAMP WITH TIME ZONE,
                        completion_timestamp TIMESTAMP WITH TIME ZONE,
                        deferral_timestamp TIMESTAMP WITH TIME ZONE,
                        room VARCHAR(255),
                        user_input TEXT,
                        user_input_en TEXT,
                        category VARCHAR(255),
                        reply TEXT,
                        is_first_baby BOOLEAN
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS assignments (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        room_number VARCHAR(255) NOT NULL,
                        nurse_name VARCHAR(255) NOT NULL,
                        UNIQUE(assignment_date, room_number)
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        event_type VARCHAR(255) NOT NULL,
                        details TEXT
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS staff (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        role VARCHAR(50) NOT NULL
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS cna_coverage (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        zone VARCHAR(10) NOT NULL CHECK (zone IN ('front','back')),
                        cna_name VARCHAR(255) NOT NULL,
                        UNIQUE (assignment_date, zone)
                    );
                """))

                # Backfill columns if the table existed before
                try:
                    connection.execute(text("ALTER TABLE requests ADD COLUMN deferral_timestamp TIMESTAMP WITH TIME ZONE;"))
                except ProgrammingError:
                    pass
                try:
                    connection.execute(text("ALTER TABLE requests ADD COLUMN user_input_en TEXT;"))
                except ProgrammingError:
                    pass

                # Seed staff if empty
                count = connection.execute(text("SELECT COUNT(id) FROM staff;")).scalar()
                if count == 0:
                    for name, role in INITIAL_STAFF.items():
                        connection.execute(text("""
                            INSERT INTO staff (name, role) VALUES (:name, :role)
                            ON CONFLICT (name) DO NOTHING;
                        """), {"name": name, "role": role})
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

setup_database()

# --- Smart Routing Logic ---
def route_note_intelligently(note_text):
    NURSE_KEYWORDS = ['pain', 'medication', 'bleeding', 'nausea', 'dizzy', 'sick', 'iv', 'pump', 'staples', 'incision']
    note_lower = note_text.lower()
    for keyword in NURSE_KEYWORDS:
        if keyword in note_lower:
            return 'nurse'
    return 'cna'

# --- Core Helper Functions ---
def log_to_audit_trail(event_type, details):
    try:
        now_utc = datetime.now(timezone.utc)
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    INSERT INTO audit_log (timestamp, event_type, details)
                    VALUES (:timestamp, :event_type, :details);
                """), {"timestamp": now_utc, "event_type": event_type, "details": details})
        socketio.emit('new_audit_log', {
            'timestamp': now_utc.strftime('%Y-%m-%d %H:%M:%S') + ' UTC',
            'event_type': event_type,
            'details': details
        })
    except Exception as e:
        print(f"ERROR logging to audit trail: {e}")

def log_request_to_db(request_id, category, user_input, user_input_en, reply, room, is_first_baby):
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    INSERT INTO requests (request_id, timestamp, room, category, user_input, user_input_en, reply, is_first_baby)
                    VALUES (:request_id, :timestamp, :room, :category, :user_input, :user_input_en, :reply, :is_first_baby);
                """), {
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc),
                    "room": room,
                    "category": category,
                    "user_input": user_input,
                    "user_input_en": user_input_en,
                    "reply": reply,
                    "is_first_baby": is_first_baby
                })
        log_to_audit_trail("Request Created", f"Room: {room}, Request: '{user_input_en}', Assigned to: {category.upper()}")
    except Exception as e:
        print(f"ERROR logging to database: {e}")

def send_email_alert(subject, body, room_number):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
    if not sender_email or not sender_password:
        return
    msg = EmailMessage()
    msg["Subject"] = f"Room {room_number} - {subject}"
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
    except Exception as e:
        print(f"ERROR: Email failed to send: {e}")

def process_request(role, subject, user_input, reply_message):
    request_id = 'req_' + str(datetime.now(timezone.utc)).replace(' ', '_').replace(':', '').replace('.', '')
    room_number = session.get('room_number', 'N/A')
    is_first_baby = session.get('is_first_baby')
    lang = session.get('language', 'en') or 'en'
    user_input_en = translate_to_en(lang, user_input)

    # Email (body keeps original), DB (store both), Socket (emit English)
    socketio.start_background_task(send_email_alert, subject, user_input, room_number)
    socketio.start_background_task(
        log_request_to_db,
        request_id, role, user_input, user_input_en, reply_message, room_number, is_first_baby
    )
    socketio.emit('new_request', {
        'id': request_id,
        'room': room_number,
        'request': user_input_en,
        'role': role,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    return reply_message

# --- App Routes ---
@app.route("/room/<room_id>")
def set_room(room_id):
    session.clear()
    session["room_number"] = room_id
    session["pathway"] = "standard"
    return redirect(url_for("language_selector"))

@app.route("/bereavement/<room_id>")
def set_bereavement_room(room_id):
    session.clear()
    session["room_number"] = room_id
    session["pathway"] = "bereavement"
    return redirect(url_for("language_selector"))

@app.route("/", methods=["GET", "POST"])
def language_selector():
    if request.method == "POST":
        session["language"] = request.form.get("language")
        pathway = session.get("pathway", "standard")
        if pathway == "bereavement":
            session["is_first_baby"] = None
            return redirect(url_for("handle_chat"))
        else:
            return redirect(url_for("demographics"))
    return render_template("language.html")

@app.route("/demographics", methods=["GET", "POST"])
def demographics():
    lang = session.get("language", "en")
    config_module_name = f"button_config_{lang}"
    try:
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data
    except (ImportError, AttributeError):
        return "Error: Language configuration file is missing or invalid."
    if request.method == "POST":
        is_first_baby_response = request.form.get("is_first_baby")
        session["is_first_baby"] = True if is_first_baby_response == 'yes' else False
        return redirect(url_for("handle_chat"))
    question_text = button_data.get("demographic_question", "Is this your first baby?")
    yes_text = button_data.get("demographic_yes", "Yes")
    no_text = button_data.get("demographic_no", "No")
    return render_template("demographics.html", question_text=question_text, yes_text=yes_text, no_text=no_text)

@app.route("/chat", methods=["GET", "POST"])
def handle_chat():
    pathway = session.get("pathway", "standard")
    lang = session.get("language", "en")
    config_module_name = f"button_config_bereavement_{lang}" if pathway == "bereavement" else f"button_config_{lang}"
    try:
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data
    except (ImportError, AttributeError) as e:
        print(f"ERROR: Could not load configuration module '{config_module_name}'. Error: {e}")
        return f"Error: Configuration file '{config_module_name}.py' is missing or invalid. Please contact support."

    if request.method == 'POST':
        if request.form.get("action") == "send_note":
            note_text = request.form.get("custom_note")
            if note_text:
                role = route_note_intelligently(note_text)
                reply_message = button_data.get(f"{role}_notification", "Your request has been sent.")
                session['reply'] = process_request(role=role, subject="Custom Patient Note", user_input=note_text, reply_message=reply_message)
                session['options'] = button_data["main_buttons"]
            else:
                session['reply'] = button_data.get("empty_custom_note", "Please type a message in the box.")
                session['options'] = button_data["main_buttons"]
        else:
            user_input = request.form.get("user_input", "").strip()
            if user_input == button_data.get("back_text", "⬅ Back"):
                session.pop('reply', None)
                session.pop('options', None)
                return redirect(url_for('handle_chat'))

            if user_input in button_data:
                button_info = button_data[user_input]
                session['reply'] = button_info.get("question") or button_info.get("note", "")
                session['options'] = button_info.get("options", [])

                back_text = button_data.get("back_text", "⬅ Back")
                if session['options'] and back_text not in session['options']:
                    session['options'].append(back_text)
                elif not session['options']:
                    session['options'] = button_data["main_buttons"]

                if "action" in button_info:
                    action = button_info["action"]
                    role = "cna" if action == "Notify CNA" else "nurse"
                    subject = f"{role.upper()} Request"
                    notification_message = button_info.get("note", button_data[f"{role}_notification"])
                    session['reply'] = process_request(role=role, subject=subject, user_input=user_input, reply_message=notification_message)
                    session['options'] = button_data["main_buttons"]
            else:
                session['reply'] = button_data.get("not_understood", "I'm sorry, I didn't understand that. Please use the buttons provided.")
                session['options'] = button_data["main_buttons"]

        return redirect(url_for('handle_chat'))

    reply = session.pop('reply', button_data["greeting"])
    options = session.pop('options', button_data["main_buttons"])
    return render_template("chat.html", reply=reply, options=options, button_data=button_data)

@app.route("/reset-language")
def reset_language():
    session.clear()
    return redirect(url_for("language_selector"))

@app.route("/dashboard")
def dashboard():
    active_requests = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT request_id,
                       room,
                       COALESCE(user_input_en, user_input) AS request_text,
                       category as role,
                       timestamp
                FROM requests
                WHERE completion_timestamp IS NULL
                ORDER BY timestamp DESC;
            """))
            for row in result:
                active_requests.append({
                    'id': row.request_id,
                    'room': row.room,
                    'request': row.request_text,
                    'role': row.role,
                    'timestamp': (row.timestamp or datetime.now(timezone.utc)).isoformat()
                })
    except Exception as e:
        print(f"ERROR fetching active requests: {e}")
    return render_template("dashboard.html", active_requests=active_requests)

@app.route('/analytics')
def analytics():
    avg_response_time = "N/A"
    top_requests_labels, top_requests_values = [], []
    most_requested_labels, most_requested_values = [], []
    requests_by_hour_labels, requests_by_hour_values = [], []
    first_baby_labels, first_baby_values = [], []
    multi_baby_labels, multi_baby_values = [], []
    try:
        with engine.connect() as connection:
            avg_time_result = connection.execute(text("""
                SELECT AVG(EXTRACT(EPOCH FROM (completion_timestamp - timestamp))) as avg_seconds
                FROM requests
                WHERE completion_timestamp IS NOT NULL;
            """)).scalar_one_or_none()
            if avg_time_result is not None:
                minutes, seconds = divmod(int(avg_time_result), 60)
                avg_response_time = f"{minutes}m {seconds}s"

            top_requests_result = connection.execute(text("""
                SELECT category, COUNT(id) FROM requests
                GROUP BY category ORDER BY COUNT(id) DESC;
            """)).fetchall()
            top_requests_labels = [row[0] for row in top_requests_result]
            top_requests_values = [row[1] for row in top_requests_result]

            most_requested_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count FROM requests
                GROUP BY user_input ORDER BY count DESC LIMIT 5;
            """)).fetchall()
            most_requested_labels = [row[0] for row in most_requested_result]
            most_requested_values = [row[1] for row in most_requested_result]

            requests_by_hour_result = connection.execute(text("""
                SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(id)
                FROM requests
                GROUP BY hour ORDER BY hour;
            """)).fetchall()
            hourly_counts = defaultdict(int)
            for hour, count in requests_by_hour_result:
                hourly_counts[int(hour)] = count
            requests_by_hour_labels = [f"{h}:00" for h in range(24)]
            requests_by_hour_values = [hourly_counts[h] for h in range(24)]

            first_baby_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests WHERE is_first_baby IS TRUE
                GROUP BY user_input ORDER BY count DESC LIMIT 5;
            """)).fetchall()
            first_baby_labels = [row[0] for row in first_baby_result]
            first_baby_values = [row[1] for row in first_baby_result]

            multi_baby_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests WHERE is_first_baby IS FALSE
                GROUP BY user_input ORDER BY count DESC LIMIT 5;
            """)).fetchall()
            multi_baby_labels = [row[0] for row in multi_baby_result]
            multi_baby_values = [row[1] for row in multi_baby_result]
    except Exception as e:
        print(f"ERROR fetching analytics data: {e}")

    return render_template(
        'analytics.html',
        avg_response_time=avg_response_time,
        top_requests_labels=top_requests_labels,
        top_requests_values=top_requests_values,
        most_requested_labels=most_requested_labels,
        most_requested_values=most_requested_values,
        requests_by_hour_labels=requests_by_hour_labels,
        requests_by_hour_values=requests_by_hour_values,
        first_baby_labels=first_baby_labels,
        first_baby_values=first_baby_values,
        multi_baby_labels=multi_baby_labels,
        multi_baby_values=multi_baby_values
    )

# --- Assignments (unchanged from your working version) ---
@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    today = date.today()

    all_nurses, all_cnas = [], []
    try:
        with engine.connect() as connection:
            nurse_rows = connection.execute(text("SELECT name FROM staff WHERE role = 'nurse' ORDER BY name;")).fetchall()
            cna_rows = connection.execute(text("SELECT name FROM staff WHERE role = 'cna' ORDER BY name;")).fetchall()
            all_nurses = [r[0] for r in nurse_rows]
            all_cnas = [r[0] for r in cna_rows]
    except Exception as e:
        print(f"ERROR fetching staff lists: {e}")

    if request.method == 'POST':
        try:
            with engine.connect() as connection:
                with connection.begin():
                    for room_number in ALL_ROOMS:
                        field = f"nurse_for_room_{room_number}"
                        nurse_name = request.form.get(field)
                        if nurse_name and nurse_name != 'unassigned':
                            connection.execute(text("""
                                INSERT INTO assignments (assignment_date, room_number, nurse_name)
                                VALUES (:date, :room, :nurse)
                                ON CONFLICT (assignment_date, room_number)
                                DO UPDATE SET nurse_name = EXCLUDED.nurse_name;
                            """), {"date": today, "room": room_number, "nurse": nurse_name})
                        else:
                            connection.execute(text("""
                                DELETE FROM assignments
                                WHERE assignment_date = :date AND room_number = :room;
                            """), {"date": today, "room": room_number})

                    cna_front = request.form.get('cna_front', 'unassigned')
                    cna_back  = request.form.get('cna_back', 'unassigned')

                    if cna_front and cna_front != 'unassigned':
                        connection.execute(text("""
                            INSERT INTO cna_coverage (assignment_date, zone, cna_name)
                            VALUES (:date, 'front', :name)
                            ON CONFLICT (assignment_date, zone)
                            DO UPDATE SET cna_name = EXCLUDED.cna_name;
                        """), {"date": today, "name": cna_front})
                    else:
                        connection.execute(text("DELETE FROM cna_coverage WHERE assignment_date=:date AND zone='front';"),
                                           {"date": today})

                    if cna_back and cna_back != 'unassigned':
                        connection.execute(text("""
                            INSERT INTO cna_coverage (assignment_date, zone, cna_name)
                            VALUES (:date, 'back', :name)
                            ON CONFLICT (assignment_date, zone)
                            DO UPDATE SET cna_name = EXCLUDED.cna_name;
                        """), {"date": today, "name": cna_back})
                    else:
                        connection.execute(text("DELETE FROM cna_coverage WHERE assignment_date=:date AND zone='back';"),
                                           {"date": today})
        except Exception as e:
            print(f"ERROR saving assignments: {e}")
        return redirect(url_for('assignments'))

    current_assignments = {}
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT room_number, nurse_name
                FROM assignments
                WHERE assignment_date = :date;
            """), {"date": today})
            for row in result:
                current_assignments[row.room_number] = row.nurse_name
    except Exception as e:
        print(f"ERROR fetching assignments: {e}")

    cna_front_val, cna_back_val = None, None
    try:
        with engine.connect() as connection:
            cov = connection.execute(text("""
                SELECT zone, cna_name FROM cna_coverage
                WHERE assignment_date = :date;
            """), {"date": today}).fetchall()
            for zone, name in cov:
                if zone == 'front':
                    cna_front_val = name
                elif zone == 'back':
                    cna_back_val = name
    except Exception as e:
        print(f"ERROR fetching CNA coverage: {e}")

    return render_template(
        'assignments.html',
        rooms=ALL_ROOMS,
        nurses=all_nurses,
        assignments=current_assignments,
        all_cnas=all_cnas,
        cna_front=cna_front_val,
        cna_back=cna_back_val
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == os.getenv('MANAGER_PASSWORD'):
            session['manager_logged_in'] = True
            return redirect(url_for('manager_dashboard'))
        else:
            flash('Invalid password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('manager_logged_in', None)
    return redirect(url_for('login'))

@app.route('/manager-dashboard', methods=['GET', 'POST'])
def manager_dashboard():
    if not session.get('manager_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            with engine.connect() as connection:
                with connection.begin():
                    if action == 'add_staff':
                        name = request.form.get('name')
                        role = request.form.get('role')
                        if name and role:
                            connection.execute(text("""
                                INSERT INTO staff (name, role) VALUES (:name, :role)
                                ON CONFLICT (name) DO NOTHING;
                            """), {"name": name, "role": role})
                            log_to_audit_trail("Staff Added", f"Added staff member: {name} ({role})")
                    elif action == 'remove_staff':
                        staff_id = request.form.get('staff_id')
                        if staff_id:
                            staff_member = connection.execute(text(
                                "SELECT name, role FROM staff WHERE id = :id;"
                            ), {"id": staff_id}).first()
                            if staff_member:
                                connection.execute(text("DELETE FROM staff WHERE id = :id;"), {"id": staff_id})
                                log_to_audit_trail("Staff Removed", f"Removed staff member: {staff_member.name} ({staff_member.role})")
        except Exception as e:
            print(f"ERROR updating staff: {e}")
        return redirect(url_for('manager_dashboard'))

    staff_list = []
    audit_log = []
    try:
        with engine.connect() as connection:
            staff_result = connection.execute(text("SELECT id, name, role FROM staff ORDER BY name;"))
            staff_list = staff_result.fetchall()
            audit_result = connection.execute(text("""
                SELECT timestamp, event_type, details FROM audit_log
                ORDER BY timestamp DESC LIMIT 50;
            """))
            audit_log = audit_result.fetchall()
    except Exception as e:
        print(f"ERROR fetching manager dashboard data: {e}")

    return render_template('manager_dashboard.html', staff=staff_list, audit_log=audit_log)

# --- SocketIO Event Handlers ---
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)

@socketio.on('acknowledge_request')
def handle_acknowledge(data):
    room = data['room']
    message = data['message']
    socketio.emit('status_update', {'message': message}, to=room)

@socketio.on('defer_request')
def handle_defer_request(data):
    request_id = data.get('id')
    if not request_id:
        return
    now_utc = datetime.now(timezone.utc)
    new_timestamp_iso = now_utc.isoformat()
    try:
        with engine.connect() as connection:
            with connection.begin():
                # Do NOT overwrite original timestamp
                connection.execute(text("""
                    UPDATE requests
                    SET category = 'nurse',
                        deferral_timestamp = :now
                    WHERE request_id = :request_id;
                """), {"now": now_utc, "request_id": request_id})
        socketio.emit('request_updated', {
            'id': request_id, 'new_role': 'nurse', 'new_timestamp': new_timestamp_iso
        })
        log_to_audit_trail("Request Deferred", f"Request ID: {request_id} deferred to NURSE.")
    except Exception as e:
        print(f"ERROR deferring request {request_id}: {e}")

@socketio.on('complete_request')
def handle_complete_request(data):
    request_id = data.get('request_id')
    if request_id:
        try:
            with engine.connect() as connection:
                trans = connection.begin()
                try:
                    connection.execute(text("""
                        UPDATE requests SET completion_timestamp = :now
                        WHERE request_id = :request_id;
                    """), {"now": datetime.now(timezone.utc), "request_id": request_id})
                    trans.commit()
                    log_to_audit_trail("Request Completed", f"Request ID: {request_id} marked as complete.")
                except Exception:
                    trans.rollback()
                    raise
            socketio.emit('remove_request', {'id': request_id})
        except Exception as e:
            print(f"ERROR updating completion timestamp: {e}")

# --- App Startup ---
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)
