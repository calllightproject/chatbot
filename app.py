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
                print("Running CREATE TABLE statements...")
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS requests (
                        id SERIAL PRIMARY KEY, request_id VARCHAR(255) UNIQUE, timestamp TIMESTAMP WITH TIME ZONE,
                        completion_timestamp TIMESTAMP WITH TIME ZONE, deferral_timestamp TIMESTAMP WITH TIME ZONE,
                        room VARCHAR(255), user_input TEXT, category VARCHAR(255), reply TEXT, is_first_baby BOOLEAN
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS assignments (
                        id SERIAL PRIMARY KEY, assignment_date DATE NOT NULL, room_number VARCHAR(255) NOT NULL,
                        staff_name VARCHAR(255) NOT NULL, UNIQUE(assignment_date, room_number)
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY, timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        event_type VARCHAR(255) NOT NULL, details TEXT
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS staff (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        role VARCHAR(50) NOT NULL
                    );
                """))
                print("CREATE TABLE statements complete.")

                count = connection.execute(text("SELECT COUNT(id) FROM staff;")).scalar()
                if count == 0:
                    print("Staff table is empty. Populating with initial staff...")
                    for name, role in INITIAL_STAFF.items():
                        connection.execute(text("""
                            INSERT INTO staff (name, role) VALUES (:name, :role)
                            ON CONFLICT (name) DO NOTHING;
                        """), {"name": name, "role": role})
                    print("Initial staff population complete.")

        with engine.connect() as connection:
            with connection.begin():
                try:
                    connection.execute(text("ALTER TABLE requests ADD COLUMN deferral_timestamp TIMESTAMP WITH TIME ZONE;"))
                except ProgrammingError:
                    pass

        print("Database setup complete. Tables are ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

setup_database()

# --- Localized label -> English maps for structured buttons ---
ES_TO_EN = {
    "Tengo una emergencia": "I'm having an emergency",
    "Necesito suministros": "I need supplies",
    "Necesito medicamentos": "I need medication",
    "Mi bomba de IV está sonando": "My IV pump is beeping",
    "Tengo preguntas": "I have questions",
    "Quiero saber sobre el alta": "I want to know about going home",
    "Baño / Ducha": "Bathroom/Shower",
    "Necesito ayuda para amamantar": "I need help breastfeeding",
    "Azúcar en la sangre": "Blood sugar",
    "Hielo / Agua": "Ice Chips/Water",

    "Mamá (azúcar en la sangre)": "Mom (blood sugar)",
    "Bebé (azúcar en la sangre)": "Baby (blood sugar)",

    "Necesito agua con hielo": "I need ice water",
    "Necesito hielo picado": "I need ice chips",
    "Necesito agua, sin hielo": "I need water, no ice",
    "Necesito agua caliente": "I need hot water",

    "Necesito ayuda para ir al baño": "I need help to the bathroom",
    "Necesito cubrir mi vía IV para bañarme": "I need my IV covered to shower",
    "¿Puedo tomar una ducha?": "Can I take a shower?",

    "Artículos para bebé": "Baby items",
    "Artículos para mamá": "Mom items",
    "Pañales": "Diapers",
    "Fórmula": "Formula",
    "Manta para envolver": "Swaddle",
    "Toallitas húmedas": "Wipes",
    "Toallas sanitarias": "Pads",
    "Ropa interior de malla": "Mesh underwear",
    "Compresa de hielo": "Ice pack",
    "Almohadas": "Pillows",

    "Toallas azules": "Blue pads",
    "Toallas blancas": "White pads",

    "Compresa de hielo para el perineo": "Ice Pack for Bottom",
    "Compresa de hielo para la incisión de la cesárea": "Ice Pack for C-section incision",
    "Compresa de hielo para los senos": "Ice Pack for Breasts",

    "Similac Total Comfort (etiqueta morada)": "Similac Total Comfort (purple label)",
    "Similac 360 (etiqueta azul)": "Similac 360 (blue label)",
    "Similac Neosure (etiqueta amarilla)": "Similac Neosure (yellow label)",
    "Enfamil Newborn (etiqueta amarilla)": "Enfamil Newborn (yellow label)",
    "Enfamil Gentlease (etiqueta morada)": "Enfamil Gentlease (purple label)",

    "Dolor": "Pain",
    "Náuseas/Vómitos": "Nausea/Vomiting",
    "Picazón": "Itchy",
    "Dolor por gases": "Gas pain",
    "Estreñimiento": "Constipation",
}

ZH_TO_EN = {
    "我有紧急情况": "I'm having an emergency",
    "我需要用品": "I need supplies",
    "我需要药物": "I need medication",
    "我的静脉输液泵在响": "My IV pump is beeping",
    "我有问题": "I have questions",
    "我想了解出院信息": "I want to know about going home",
    "浴室/淋浴": "Bathroom/Shower",
    "我需要母乳喂养方面的帮助": "I need help breastfeeding",
    "血糖": "Blood sugar",
    "冰块/水": "Ice Chips/Water",

    "妈妈（血糖）": "Mom (blood sugar)",
    "宝宝（血糖）": "Baby (blood sugar)",

    "我需要冰水": "I need ice water",
    "我需要冰块": "I need ice chips",
    "我需要不加冰的水": "I need water, no ice",
    "我需要热水": "I need hot water",

    "我需要帮助去卫生间": "I need help to the bathroom",
    "我需要包裹我的静脉输液管以便洗澡": "I need my IV covered to shower",
    "我可以洗澡吗？": "Can I take a shower?",

    "宝宝用品": "Baby items",
    "妈妈用品": "Mom items",
    "尿布": "Diapers",
    "配方奶": "Formula",
    "襁褓巾": "Swaddle",
    "湿巾": "Wipes",
    "卫生巾": "Pads",
    "网眼内裤": "Mesh underwear",
    "冰袋": "Ice pack",
    "枕头": "Pillows",

    "蓝色卫生巾": "Blue pads",
    "白色卫生巾": "White pads",

    "用于会阴部的冰袋": "Ice Pack for Bottom",
    "用于剖腹产切口的冰袋": "Ice Pack for C-section incision",
    "用于乳房的冰袋": "Ice Pack for Breasts",

    "Similac Total Comfort (紫色标签)": "Similac Total Comfort (purple label)",
    "Similac 360 (蓝色标签)": "Similac 360 (blue label)",
    "Similac Neosure (黄色标签)": "Similac Neosure (yellow label)",
    "Enfamil Newborn (黄色标签)": "Enfamil Newborn (yellow label)",
    "Enfamil Gentlease (紫色标签)": "Enfamil Gentlease (purple label)",

    "疼痛": "Pain",
    "恶心/呕吐": "Nausea/Vomiting",
    "瘙痒": "Itchy",
    "胀气痛": "Gas pain",
    "便秘": "Constipation",
}

def to_english_label(text: str, lang: str) -> str:
    """Return an English label for structured buttons. For unknown/custom notes, tag language."""
    if not text:
        return text
    if lang == "es":
        return ES_TO_EN.get(text, f"[ES] {text}")
    if lang == "zh":
        return ZH_TO_EN.get(text, f"[ZH] {text}")
    return text

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
                """), {
                    "timestamp": now_utc,
                    "event_type": event_type,
                    "details": details
                })

        socketio.emit('new_audit_log', {
            'timestamp': now_utc.strftime('%Y-%m-%d %H:%M:%S') + ' UTC',
            'event_type': event_type,
            'details': details
        })

    except Exception as e:
        print(f"ERROR logging to audit trail: {e}")

def log_request_to_db(request_id, category, user_input, reply, room, is_first_baby):
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    INSERT INTO requests (request_id, timestamp, room, category, user_input, reply, is_first_baby)
                    VALUES (:request_id, :timestamp, :room, :category, :user_input, :reply, :is_first_baby);
                """), {
                    "request_id": request_id, "timestamp": datetime.now(timezone.utc), "room": room,
                    "category": category, "user_input": user_input, "reply": reply, "is_first_baby": is_first_baby
                })
        log_to_audit_trail("Request Created", f"Room: {room}, Request: '{user_input}', Assigned to: {category.upper()}")
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
    # Normalize to English for dashboard/email/logs; tag unknown custom notes with language
    lang = session.get('language', 'en')
    english_user_input = to_english_label(user_input, lang)

    request_id = 'req_' + str(datetime.now(timezone.utc).timestamp()).replace('.', '')
    room_number = session.get('room_number', 'N/A')
    is_first_baby = session.get('is_first_baby')

    socketio.start_background_task(send_email_alert, subject, english_user_input, room_number)
    socketio.start_background_task(
        log_request_to_db,
        request_id,
        role,
        english_user_input,  # store/emit English text
        reply_message,
        room_number,
        is_first_baby
    )
    socketio.emit('new_request', {
        'id': request_id, 'room': room_number, 'request': english_user_input,
        'role': role, 'timestamp': datetime.now(timezone.utc).isoformat()
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
                # Use localized empty message if present; fall back to English
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
                session['reply'] = button_data.get("fallback_unrecognized", "I'm sorry, I didn't understand that. Please use the buttons provided.")
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
                SELECT request_id, room, user_input, category as role, timestamp
                FROM requests
                WHERE completion_timestamp IS NULL
                ORDER BY timestamp DESC;
            """))
            for row in result:
                active_requests.append({
                    'id': row.request_id,
                    'room': row.room,
                    'request': row.user_input,
                    'role': row.role,
                    'timestamp': row.timestamp.isoformat()
                })
    except Exception as e:
        print(f"ERROR fetching active requests: {e}")
    return render_template("dashboard.html", active_requests=active_requests)

# --- Analytics ---
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
                GROUP BY category
                ORDER BY COUNT(id) DESC;
            """)).fetchall()
            top_requests_labels = [row[0] for row in top_requests_result]
            top_requests_values = [row[1] for row in top_requests_result]

            most_requested_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests
                GROUP BY user_input
                ORDER BY count DESC
                LIMIT 5;
            """)).fetchall()
            most_requested_labels = [row[0] for row in most_requested_result]
            most_requested_values = [row[1] for row in most_requested_result]

            requests_by_hour_result = connection.execute(text("""
                SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(id)
                FROM requests
                GROUP BY hour
                ORDER BY hour;
            """)).fetchall()
            hourly_counts = defaultdict(int)
            for hour, count in requests_by_hour_result:
                hourly_counts[int(hour)] = count
            requests_by_hour_labels = [f"{h}:00" for h in range(24)]
            requests_by_hour_values = [hourly_counts[h] for h in range(24)]

            first_baby_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests
                WHERE is_first_baby IS TRUE
                GROUP BY user_input
                ORDER BY count DESC
                LIMIT 5;
            """)).fetchall()
            first_baby_labels = [row[0] for row in first_baby_result]
            first_baby_values = [row[1] for row in first_baby_result]

            multi_baby_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests
                WHERE is_first_baby IS FALSE
                GROUP BY user_input
                ORDER BY count DESC
                LIMIT 5;
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
# --- Assignments (shift-aware; CNA zones; strict nurse filtering) ---
@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    today = date.today()

    # Normalize the shift to lowercase and default to 'day'
    if request.method == 'GET':
        shift = (request.args.get('shift') or 'day').lower()
    else:
        shift = (request.form.get('shift') or 'day').lower()
    if shift not in ('day', 'night'):
        shift = 'day'

    # ---------- Load nurses, grouped by preferred_shift (strict) ----------
    nurses_by_shift = {'day': [], 'night': [], 'unspecified': []}
    preferred_nurses = []
    other_nurses = []
    all_nurses = []  # not used by template, but harmless to keep

    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT
                    name,
                    LOWER(TRIM(COALESCE(preferred_shift, 'unspecified'))) AS pref
                FROM staff
                WHERE role = 'nurse'
                ORDER BY name;
            """)).fetchall()

        for name, pref in rows:
            if not name or name.strip().lower() == 'unassigned':
                continue
            all_nurses.append(name)
            if pref not in ('day', 'night'):
                pref = 'unspecified'
            nurses_by_shift[pref].append(name)

        # Strict filtering: only the selected shift; optionally include 'unspecified'
        preferred_nurses = sorted(nurses_by_shift.get(shift, []))
        other_nurses = sorted(nurses_by_shift.get('unspecified', []))  # keep or set [] to hide

        print(f"[assignments] shift={shift} -> day={len(nurses_by_shift['day'])}, "
              f"night={len(nurses_by_shift['night'])}, "
              f"unspec={len(nurses_by_shift['unspecified'])}; "
              f"preferred={len(preferred_nurses)}, other={len(other_nurses)}")

    except Exception as e:
        print(f"ERROR fetching nurses: {e}")
        preferred_nurses = []
        other_nurses = []

    # ---------- Handle save ----------
    if request.method == 'POST':
        try:
            with engine.connect() as connection:
                with connection.begin():
                    # Save nurse-by-room (shift-aware)
                    for room_number in ALL_ROOMS:
                        staff_name = request.form.get(f'nurse_for_room_{room_number}')
                        if staff_name and staff_name != 'unassigned':
                            connection.execute(text("""
                                INSERT INTO assignments (assignment_date, shift, room_number, staff_name)
                                VALUES (:date, :shift, :room, :nurse)
                                ON CONFLICT (assignment_date, shift, room_number)
                                DO UPDATE SET staff_name = EXCLUDED.staff_name;
                            """), {"date": today, "shift": shift, "room": room_number, "nurse": staff_name})
                        else:
                            connection.execute(text("""
                                DELETE FROM assignments
                                WHERE assignment_date = :date
                                  AND shift = :shift
                                  AND room_number = :room;
                            """), {"date": today, "shift": shift, "room": room_number})

                    # Save CNA coverage as zone rows (front/back), shift-aware
                    cna_front_form = request.form.get('cna_front', 'unassigned')
                    cna_back_form  = request.form.get('cna_back',  'unassigned')
                    cna_front_db = None if cna_front_form == 'unassigned' else cna_front_form
                    cna_back_db  = None if cna_back_form  == 'unassigned' else cna_back_form

                    for zone, name in [('front', cna_front_db), ('back', cna_back_db)]:
                        connection.execute(text("""
                            INSERT INTO cna_coverage (assignment_date, shift, zone, cna_name)
                            VALUES (:date, :shift, :zone, :name)
                            ON CONFLICT (assignment_date, shift, zone)
                            DO UPDATE SET cna_name = EXCLUDED.cna_name;
                        """), {"date": today, "shift": shift, "zone": zone, "name": name})

            print(f"Assignments saved successfully for shift={shift}.")
        except Exception as e:
            print(f"ERROR saving assignments: {e}")

        # Preserve selected shift after save
        return redirect(url_for('assignments', shift=shift))

    # ---------- Load CNAs for dropdown ----------
    all_cnas = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT name FROM staff WHERE role = 'cna' ORDER BY name;")
            ).fetchall()
            all_cnas = [r[0] for r in rows if r[0] and r[0].strip().lower() != 'unassigned']
    except Exception as e:
        print(f"ERROR fetching CNAs: {e}")

    # ---------- Read back today's nurse assignments for this shift ----------
    current_assignments = {}
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT room_number, staff_name
                FROM assignments
                WHERE assignment_date = :date AND shift = :shift;
            """), {"date": today, "shift": shift}).fetchall()
            for r in rows:
                current_assignments[r.room_number] = r.staff_name
    except Exception as e:
        print(f"ERROR fetching assignments: {e}")

    # ---------- Read back today's CNA coverage for this shift ----------
    cna_front_val = 'unassigned'
    cna_back_val  = 'unassigned'
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT zone, cna_name
                FROM cna_coverage
                WHERE assignment_date = :date AND shift = :shift;
            """), {"date": today, "shift": shift}).fetchall()
            zmap = {(r[0] or '').lower(): r[1] for r in rows}
            cna_front_val = zmap.get('front') or 'unassigned'
            cna_back_val  = zmap.get('back')  or 'unassigned'
    except Exception as e:
        print(f"INFO fetching CNA coverage: {e}")

    # ---------- Render ----------
    return render_template(
        'assignments.html',
        all_rooms=ALL_ROOMS,
        # only these two are used by the template for nurse dropdowns:
        preferred_nurses=preferred_nurses,
        other_nurses=other_nurses,
        current_assignments=current_assignments,
        all_cnas=all_cnas,
        cna_front=cna_front_val,
        cna_back=cna_back_val,
        shift=shift
    )


#DEBUGDEBUGDEBUG

@app.route("/health")
def health():
    return "ok", 200



# --- Auth for Manager (unchanged) ---
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
        action = (request.form.get('action') or '').strip()
        try:
            with engine.connect() as connection:
                with connection.begin():
                    if action == 'add_staff':
                        # Read & normalize inputs
                        name = (request.form.get('name') or '').strip()
                        role = (request.form.get('role') or 'nurse').strip().lower()
                        if role not in ('nurse', 'cna'):
                            role = 'nurse'

                        # '', 'unspecified', None => store as NULL
                        pref_raw = (request.form.get('preferred_shift') or '').strip().lower()
                        if pref_raw in ('day', 'night'):
                            preferred_shift = pref_raw
                        else:
                            preferred_shift = None  # will store NULL

                        if name:
                            # Upsert on name so edits are easy from the UI
                            connection.execute(text("""
                                INSERT INTO staff (name, role, preferred_shift)
                                VALUES (:name, :role, :preferred_shift)
                                ON CONFLICT (name) DO UPDATE
                                SET role = EXCLUDED.role,
                                    preferred_shift = EXCLUDED.preferred_shift;
                            """), {
                                "name": name,
                                "role": role,
                                "preferred_shift": preferred_shift
                            })

                            log_to_audit_trail(
                                "Staff Added",
                                f"Added/updated staff: {name} ({role}, pref_shift={preferred_shift or 'unspecified'})"
                            )

                    elif action == 'remove_staff':
                        staff_id = request.form.get('staff_id')
                        if staff_id:
                            staff_member = connection.execute(
                                text("SELECT name, role FROM staff WHERE id = :id;"),
                                {"id": staff_id}
                            ).first()

                            connection.execute(
                                text("DELETE FROM staff WHERE id = :id;"),
                                {"id": staff_id}
                            )

                            if staff_member:
                                log_to_audit_trail(
                                    "Staff Removed",
                                    f"Removed staff member: {staff_member.name} ({staff_member.role})"
                                )

        except Exception as e:
            print(f"ERROR updating staff: {e}")

        return redirect(url_for('manager_dashboard'))

    # ----- GET: fetch staff + recent audit log -----
    staff_list = []
    audit_log = []
    try:
        with engine.connect() as connection:
            staff_result = connection.execute(
                text("SELECT id, name, role, preferred_shift FROM staff ORDER BY name;")
            )
            staff_list = staff_result.fetchall()

            audit_result = connection.execute(text("""
                SELECT timestamp, event_type, details
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT 50;
            """))
            audit_log = audit_result.fetchall()
    except Exception as e:
        print(f"ERROR fetching manager dashboard data: {e}")

    return render_template('manager_dashboard.html', staff=staff_list, audit_log=audit_log)


# --- Staff Portal (PIN + nurse-specific dashboard) ---
@app.route('/staff-portal', methods=['GET', 'POST'])
def staff_portal():
    pin_required = os.getenv("STAFF_PORTAL_PIN")
    if request.method == 'POST':
        entered_pin = request.form.get('pin', '').strip()
        if pin_required and entered_pin != pin_required:
            flash("Invalid PIN.", "danger")
            return render_template('staff_portal.html')
        staff_name = request.form.get('staff_name', '').strip()
        if staff_name:
            return redirect(url_for('staff_dashboard_for_nurse', staff_name=staff_name))
        else:
            flash("Please enter your name.", "danger")
    return render_template('staff_portal.html')

@app.route('/staff/dashboard/<staff_name>')
def staff_dashboard_for_nurse(staff_name):
    today = date.today()
    # Find this nurse's rooms for today
    rooms_for_nurse = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT room_number FROM assignments
                WHERE assignment_date = :d AND staff_name = :n
                ORDER BY room_number;
            """), {"d": today, "n": staff_name}).fetchall()
            rooms_for_nurse = [r[0] for r in rows]
    except Exception as e:
        print(f"ERROR fetching rooms for nurse {staff_name}: {e}")

    # Get active requests limited to these rooms
    active_requests = []
    if rooms_for_nurse:
        try:
            with engine.connect() as connection:
                result = connection.execute(text(f"""
                    SELECT request_id, room, user_input, category as role, timestamp
                    FROM requests
                    WHERE completion_timestamp IS NULL
                      AND room = ANY(:room_list)
                    ORDER BY timestamp DESC;
                """), {"room_list": rooms_for_nurse})
                for row in result:
                    active_requests.append({
                        'id': row.request_id,
                        'room': row.room,
                        'request': row.user_input,
                        'role': row.role,
                        'timestamp': row.timestamp.isoformat()
                    })
        except Exception as e:
            print(f"ERROR fetching nurse dashboard requests: {e}")

    return render_template("dashboard.html",
                           active_requests=active_requests,
                           nurse_view=True,
                           staff_name=staff_name





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
                # IMPORTANT: do NOT overwrite original timestamp; only set category + deferral_timestamp
                connection.execute(text("""
                    UPDATE requests
                    SET category = 'nurse', deferral_timestamp = :now
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
                        UPDATE requests
                        SET completion_timestamp = :now
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
































