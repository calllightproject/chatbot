import eventlet
eventlet.monkey_patch()

import os
import json
import smtplib
import importlib
from datetime import datetime, date, time, timezone
from collections import defaultdict
from email.message import EmailMessage

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, abort
from flask_socketio import SocketIO, join_room
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from werkzeug.security import generate_password_hash, check_password_hash

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")
socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    manage_session=False,
    ping_timeout=60,   # was 20
    ping_interval=25   # was 10
)

# --- Room Configuration ---
ALL_ROOMS = [str(room) for room in range(231, 260)]
VALID_ROOMS = set(ALL_ROOMS)

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

                # Core tables
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS requests (
                        id SERIAL PRIMARY KEY,
                        request_id VARCHAR(255) UNIQUE,
                        timestamp TIMESTAMPTZ,
                        completion_timestamp TIMESTAMPTZ,
                        deferral_timestamp TIMESTAMPTZ,
                        room VARCHAR(255),
                        user_input TEXT,
                        category VARCHAR(255),
                        reply TEXT,
                        is_first_baby BOOLEAN
                    );
                """))

                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS assignments (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        shift VARCHAR(10) NOT NULL,
                        room_number VARCHAR(255) NOT NULL,
                        staff_name VARCHAR(255) NOT NULL,
                        UNIQUE (assignment_date, shift, room_number)
                    );
                """))

                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL,
                        event_type VARCHAR(255) NOT NULL,
                        details TEXT
                    );
                """))

                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS staff (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        role VARCHAR(50) NOT NULL,
                        preferred_shift VARCHAR(10),
                        languages TEXT,
                        pin_hash TEXT,
                        pin_set_at TIMESTAMPTZ
                    );
                """))

                # CNA coverage (front/back per shift)
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS cna_coverage (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        shift VARCHAR(10) NOT NULL,
                        zone VARCHAR(20) NOT NULL,   -- 'front' / 'back'
                        cna_name VARCHAR(255),
                        UNIQUE (assignment_date, shift, zone)
                    );
                """))

                # Room state: reset marker + future tags (JSONB)
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS room_state (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        shift VARCHAR(10) NOT NULL,
                        room_number VARCHAR(20) NOT NULL,
                        reset_at TIMESTAMPTZ,
                        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                        UNIQUE (assignment_date, shift, room_number)
                    );
                """))

                print("CREATE TABLE statements complete.")

                # ---------------- Idempotent hardening ----------------

                # Ensure 'shift' column exists on older DBs (harmless if already there)
                try:
                    connection.execute(text("""
                        ALTER TABLE assignments
                        ADD COLUMN IF NOT EXISTS shift VARCHAR(10) NOT NULL DEFAULT 'day';
                    """))
                    connection.execute(text("""
                        ALTER TABLE assignments
                        ALTER COLUMN shift DROP DEFAULT;
                    """))
                except Exception:
                    pass

                # Ensure correct UNIQUE(date, shift, room) on assignments
                try:
                    connection.execute(text("""
                        DO $$
                        BEGIN
                          IF NOT EXISTS (
                            SELECT 1
                            FROM   pg_constraint
                            WHERE  conname = 'assignments_uniq_date_shift_room'
                          ) THEN
                            ALTER TABLE assignments
                            ADD CONSTRAINT assignments_uniq_date_shift_room
                            UNIQUE (assignment_date, shift, room_number);
                          END IF;
                        END$$;
                    """))
                except Exception:
                    pass

                # Backfill safe defaults
                try:
                    connection.execute(text("""
                        UPDATE room_state
                        SET tags = COALESCE(tags, '[]'::jsonb);
                    """))
                except Exception:
                    pass

                try:
                    connection.execute(text("""
                        UPDATE staff
                        SET languages = COALESCE(languages, '["en"]');
                    """))
                except Exception:
                    pass

                # Ensure PIN columns exist on older DBs
                try:
                    connection.execute(text("""
                        ALTER TABLE staff
                        ADD COLUMN IF NOT EXISTS pin_hash TEXT;
                    """))
                    connection.execute(text("""
                        ALTER TABLE staff
                        ADD COLUMN IF NOT EXISTS pin_set_at TIMESTAMPTZ;
                    """))
                except Exception:
                    pass

        # Legacy safety: make sure deferral_timestamp exists
        try:
            with engine.connect() as connection:
                with connection.begin():
                    connection.execute(text("""
                        ALTER TABLE requests
                        ADD COLUMN IF NOT EXISTS deferral_timestamp TIMESTAMPTZ;
                    """))
        except Exception:
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

# ---- General helpers --------------------------------------------------------
def _valid_room(room_str: str) -> bool:
    if not room_str or not str(room_str).isdigit():
        return False
    n = int(room_str)
    return 231 <= n <= 260

def _current_room() -> str | None:
    """
    Prefer session, but allow override via ?room=XYZ for testing.
    If a valid ?room= is passed, persist it into the session.
    """
    room = request.args.get("room") or session.get("room_number")
    if room and _valid_room(str(room)):
        room_str = str(room)
        if session.get("room_number") != room_str:
            session["room_number"] = room_str
        return room_str
    return None

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

def emit_patient_event(event: str, room_number: str | int, payload: dict):
    """Emit an event to the patient's socket.io room."""
    socketio.emit(
        event,
        {"room_id": str(room_number), **(payload or {})},
        to=f"patient:{room_number}",
        namespace="/patient",
    )

def _get_room_for_request(request_id: str | int) -> str | None:
    """Look up room number for a given request_id from the requests table."""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT room FROM requests WHERE request_id = :rid LIMIT 1"),
                {"rid": request_id},
            ).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception as e:
        print(f"ERROR reading room for request {request_id}: {e}")
    return None

def send_email_alert(subject, body, room_number):
    """Safe/no-op email alert. Will quietly skip if creds aren’t set."""
    try:
        sender_email = os.getenv("EMAIL_USER")
        sender_password = os.getenv("EMAIL_PASSWORD")
        recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
        if not sender_email or not sender_password:
            return  # no creds → skip
        msg = EmailMessage()
        msg["Subject"] = f"Room {room_number} - {subject}"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
    except Exception as e:
        print(f"EMAIL disabled or failed: {e}")

# --- Smart Routing Logic ---
def route_note_intelligently(note_text):
    NURSE_KEYWORDS = [
        'pain', 'medication', 'bleeding', 'nausea', 'dizzy', 'sick',
        'iv', 'pump', 'staples', 'incision', 'nipple', 'nipples',
        'heavy', 'golf ball', 'meds', 'breastfeeding'
    ]
    note_lower = note_text.lower()
    for keyword in NURSE_KEYWORDS:
        if keyword in note_lower:
            return 'nurse'
    return 'cna'

# --- Persistence for requests ---
def log_request_to_db(request_id, category, user_input, reply, room, is_first_baby):
    """Persist a request and emit a clear server-side debug line showing the resolved room."""
    try:
        room_str = str(room).strip() if room is not None else None
        is_digit = room_str.isdigit() if room_str else False
        is_valid_room = is_digit and 231 <= int(room_str) <= 260

        if is_valid_room:
            print(f"[log_request_to_db] OK  | request_id={request_id} room={room_str} role={category}")
        else:
            print(f"[log_request_to_db] WARN| request_id={request_id} invalid/unknown room='{room_str}' role={category}")

        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    INSERT INTO requests (request_id, timestamp, room, category, user_input, reply, is_first_baby)
                    VALUES (:request_id, :timestamp, :room, :category, :user_input, :reply, :is_first_baby);
                """), {
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc),
                    "room": room_str,
                    "category": category,
                    "user_input": user_input,
                    "reply": reply,
                    "is_first_baby": is_first_baby
                })

        log_to_audit_trail(
            "Request Created",
            f"Room: {room_str or 'N/A'}, Request: '{user_input}', Assigned to: {category.upper()}"
        )
    except Exception as e:
        print(f"ERROR logging to database: {e}")

def process_request(role, subject, user_input, reply_message):
    lang = session.get('language', 'en')
    english_user_input = to_english_label(user_input, lang)

    request_id = 'req_' + str(datetime.now(timezone.utc).timestamp()).replace('.', '')

    # Prefer _current_room (checks ?room=XYZ and session), fallback to None
    room_number = _current_room() or session.get('room_number')
    if not room_number or not _valid_room(room_number):
        room_number = None

    is_first_baby = session.get('is_first_baby')

    # Background tasks
    socketio.start_background_task(
        log_request_to_db,
        request_id,
        role,
        english_user_input,
        reply_message,
        room_number,
        is_first_baby
    )

    # Optional: email alert
    # socketio.start_background_task(
    #     send_email_alert, subject, english_user_input, room_number or "Unknown"
    # )

    # Broadcast to dashboards
    socketio.emit('new_request', {
        'id': request_id,
        'room': room_number,   # None if unknown
        'request': english_user_input,
        'role': role,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

    return reply_message

def _emit_received_for(room_number: str, user_text: str, kind: str):
    """Look up the most recent matching request row and emit to the patient room."""
    if not (room_number and user_text):
        return
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT request_id, timestamp
                FROM requests
                WHERE room = :room AND user_input = :txt
                ORDER BY timestamp DESC
                LIMIT 1
            """), {"room": str(room_number), "txt": user_text}).fetchone()
        if row and row.request_id:
            emit_patient_event("request:received", room_number, {
                "request_id": row.request_id,
                "kind": kind,  # "note" or "option"
                "note": user_text if kind == "note" else "",
                "created_at": (row.timestamp or datetime.now(timezone.utc)).isoformat()
            })
    except Exception as e:
        print(f"WARN: could not emit request:received for room {room_number}: {e}")

# --- Routes ------------------------------------------------------------------

# Standard room entry (clears state, sets STANDARD)
@app.route("/room/<room_id>")
def set_room(room_id):
    if not _valid_room(room_id):
        abort(404)
    session.clear()
    session["room_number"] = str(room_id)
    session["pathway"] = "standard"
    return redirect(url_for("language_selector"))

# Bereavement room entry (clears state, sets BEREAVEMENT)
@app.route("/bereavement/<room_id>")
def set_bereavement_room(room_id):
    if not _valid_room(room_id):
        abort(404)
    session.clear()
    session["room_number"] = str(room_id)
    session["pathway"] = "bereavement"
    return redirect(url_for("language_selector"))

@app.route("/", methods=["GET", "POST"])
def language_selector():
    if request.method == "POST":
        session["language"] = request.form.get("language")
        pathway = session.get("pathway", "standard")
        if pathway == "bereavement":
            session["is_first_baby"] = None
            return redirect(url_for("handle_chat", room=session.get("room_number")))
        else:
            return redirect(url_for("demographics", room=session.get("room_number")))
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
        return redirect(url_for("handle_chat", room=session.get("room_number")))
    question_text = button_data.get("demographic_question", "Is this your first baby?")
    yes_text = button_data.get("demographic_yes", "Yes")
    no_text = button_data.get("demographic_no", "No")
    return render_template("demographics.html", question_text=question_text, yes_text=yes_text, no_text=no_text)

@app.route("/chat", methods=["GET", "POST"])
def handle_chat():
    # Pathway resolution:
    # 1) If ?pathway= is present and valid, use it and update session
    # 2) Else use session (default 'standard' if missing)
    qp = (request.args.get("pathway") or "").strip().lower()
    if qp in ("standard", "bereavement"):
        session["pathway"] = qp
    pathway = session.get("pathway", "standard")

    lang = session.get("language", "en")

    # Load the correct button config module based on pathway + language
    config_module_name = (
        f"button_config_bereavement_{lang}"
        if pathway == "bereavement"
        else f"button_config_{lang}"
    )
    try:
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data
    except (ImportError, AttributeError) as e:
        print(f"ERROR: Could not load configuration module '{config_module_name}'. Error: {e}")
        return (
            f"Error: Configuration file '{config_module_name}.py' is missing or invalid. "
            "Please contact support."
        )

    # Resolve room number from ?room=, session, or POST
    room_number = _current_room()
    room_from_form = (request.form.get("room") or "").strip() if request.method == "POST" else ""
    if room_from_form and _valid_room(room_from_form):
        session["room_number"] = room_from_form
        room_number = room_from_form

    if room_number and session.get("room_number") != room_number:
        session["room_number"] = room_number

    if request.method == "POST":
        # Free-text note path
        if request.form.get("action") == "send_note":
            note_text = (request.form.get("custom_note") or "").strip()
            if note_text:
                role = route_note_intelligently(note_text)  # "nurse" or "cna"
                reply_message = button_data.get(f"{role}_notification", "Your request has been sent.")

                session["reply"] = process_request(
                    role=role,
                    subject="Custom Patient Note",
                    user_input=note_text,
                    reply_message=reply_message,
                )
                session["options"] = button_data["main_buttons"]

                if room_number:
                    _emit_received_for(room_number, note_text, kind="note")
            else:
                session["reply"] = button_data.get("empty_custom_note", "Please type a message in the box.")
                session["options"] = button_data["main_buttons"]

        # Button click path
        else:
            user_input = (request.form.get("user_input") or "").strip()

            # Back / home
            if user_input == button_data.get("back_text", "⬅ Back"):
                session.pop("reply", None)
                session.pop("options", None)
                return redirect(url_for("handle_chat", room=room_number) if room_number else url_for("handle_chat"))

            # Known button
            if user_input in button_data:
                button_info = button_data[user_input]
                session["reply"] = button_info.get("question") or button_info.get("note", "")
                session["options"] = button_info.get("options", [])

                back_text = button_data.get("back_text", "⬅ Back")
                if session["options"] and back_text not in session["options"]:
                    session["options"].append(back_text)
                elif not session["options"]:
                    session["options"] = button_data["main_buttons"]

                # Action button -> notify CNA/Nurse + log
                if "action" in button_info:
                    action = button_info["action"]
                    role = "cna" if action in ("Notify CNA", "通知护理助理", "Notificar al asistente de enfermería") else "nurse"
                    subject = f"{role.upper()} Request"
                    notification_message = button_info.get("note", button_data.get(f"{role}_notification", "Your request has been sent."))

                    session["reply"] = process_request(
                        role=role,
                        subject=subject,
                        user_input=user_input,
                        reply_message=notification_message,
                    )
                    session["options"] = button_data["main_buttons"]

                    if room_number:
                        _emit_received_for(room_number, user_input, kind="option")

            # Unknown input
            else:
                session["reply"] = button_data.get(
                    "fallback_unrecognized",
                    "I'm sorry, I didn't understand that. Please use the buttons provided.",
                )
                session["options"] = button_data["main_buttons"]

        # Always redirect after POST (PRG)
        return redirect(url_for("handle_chat", room=room_number) if room_number else url_for("handle_chat"))

    # --- GET: render page ---
    reply = session.pop("reply", button_data["greeting"])
    options = session.pop("options", button_data["main_buttons"])
    return render_template(
        "chat.html",
        reply=reply,
        options=options,
        button_data=button_data,
        room_number=room_number,  # used by chat.html Socket.IO connect
    )

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
                SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                       room, user_input, category as role, timestamp
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
                    'timestamp': row.timestamp.isoformat() if row.timestamp else None
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

    # Normalize the shift (default day)
    if request.method == 'GET':
        shift = (request.args.get('shift') or 'day').lower()
    else:
        shift = (request.form.get('shift') or 'day').lower()
    if shift not in ('day', 'night'):
        shift = 'day'

    # ---------- Load nurses grouped by preferred_shift ----------
    nurses_by_shift = {'day': [], 'night': [], 'unspecified': []}
    preferred_nurses, other_nurses, opposite_nurses = [], [], []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT
                    name,
                    CASE
                      WHEN preferred_shift IS NULL OR TRIM(preferred_shift) = '' THEN 'unspecified'
                      ELSE LOWER(TRIM(BOTH '''' FROM preferred_shift))
                    END AS pref
                FROM staff
                WHERE LOWER(role) = 'nurse'
                ORDER BY name;
            """)).fetchall()

        for name, pref in rows:
            if not name or name.strip().lower() == 'unassigned':
                continue
            if pref not in ('day', 'night'):
                pref = 'unspecified'
            nurses_by_shift[pref].append(name)

        preferred_nurses = sorted(nurses_by_shift.get(shift, []))
        other_nurses = sorted(nurses_by_shift.get('unspecified', []))
        opp = 'night' if shift == 'day' else 'day'
        opposite_nurses = sorted(nurses_by_shift.get(opp, []))
    except Exception:
        preferred_nurses, other_nurses, opposite_nurses = [], [], []

    # ---------- Save (POST) ----------
    if request.method == 'POST':
        # 1) Save nurse-by-room (own transaction)
        try:
            with engine.connect() as connection:
                with connection.begin():
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
        except Exception as e:
            print(f"ERROR saving nurse assignments: {e}")

        # 2) Save CNA coverage (separate transaction; DELETE→INSERT)
        try:
            cna_front_form = request.form.get('cna_front', 'unassigned')
            cna_back_form  = request.form.get('cna_back',  'unassigned')
            cna_front_db = None if cna_front_form == 'unassigned' else cna_front_form
            cna_back_db  = None if cna_back_form  == 'unassigned' else cna_back_form

            with engine.connect() as connection:
                with connection.begin():
                    for zone, name in [('front', cna_front_db), ('back', cna_back_db)]:
                        connection.execute(text("""
                            DELETE FROM cna_coverage
                            WHERE assignment_date = :date AND shift = :shift AND zone = :zone;
                        """), {"date": today, "shift": shift, "zone': zone})
                        connection.execute(text("""
                            INSERT INTO cna_coverage (assignment_date, shift, zone, cna_name)
                            VALUES (:date, :shift, :zone, :name);
                        """), {"date": today, "shift": shift, "zone": zone, "name": name})
        except Exception as e:
            print(f"ERROR saving CNA coverage (ignored): {e}")

        return redirect(url_for('assignments', shift=shift))

    # ---------- Load CNAs for dropdown ----------
    all_cnas = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT name
                FROM staff
                WHERE LOWER(role) = 'cna'
                ORDER BY name;
            """)).fetchall()
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
                current_assignments[r.room_number] = r[1] if isinstance(r, tuple) else r.staff_name
    except Exception as e:
        print(f"ERROR fetching assignments: {e}")

    # ---------- Read back today's CNA coverage for this shift ----------
    cna_front_val, cna_back_val = 'unassigned', 'unassigned'
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
        preferred_nurses=preferred_nurses,
        other_nurses=other_nurses,
        opposite_nurses=opposite_nurses,
        current_assignments=current_assignments,
        all_cnas=all_cnas,
        cna_front=cna_front_val,
        cna_back=cna_back_val,
        shift=shift
    )

@app.route('/room/reset', methods=['POST'])
def room_reset():
    """Mark a room as 'reset' (new patient) and clear its nurse assignment for today's selected shift."""
    try:
        today = date.today()
        shift = (request.form.get('shift') or 'day').lower()
        room = (request.form.get('room') or '').strip()

        if shift not in ('day', 'night') or not room:
            return redirect(url_for('assignments', shift=shift or 'day'))

        with engine.connect() as connection:
            with connection.begin():
                # 1) Upsert room_state (preserve existing tags, bump reset_at)
                connection.execute(text("""
                    INSERT INTO room_state (assignment_date, shift, room_number, reset_at, tags)
                    VALUES (:d, :s, :r, NOW(),
                        COALESCE((SELECT tags FROM room_state
                                  WHERE assignment_date = :d AND shift = :s AND room_number = :r),
                                 '[]'))
                    ON CONFLICT (assignment_date, shift, room_number)
                    DO UPDATE SET reset_at = EXCLUDED.reset_at;
                """), {"d": today, "s": shift, "r": room})

                # 2) Clear any nurse assignment for this room/shift/date
                connection.execute(text("""
                    DELETE FROM assignments
                    WHERE assignment_date = :d AND shift = :s AND room_number = :r;
                """), {"d": today, "s": shift, "r": room})

        return redirect(url_for('assignments', shift=shift))

    except Exception as e:
        print(f"ERROR in /room/reset: {e}")
        return redirect(url_for('assignments', shift=(request.form.get('shift') or 'day').lower()))

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
                        name = (request.form.get('name') or '').strip()
                        role = (request.form.get('role') or 'nurse').strip().lower()
                        if role not in ('nurse', 'cna'):
                            role = 'nurse'

                        pref_raw = (request.form.get('preferred_shift') or '').strip().lower()
                        preferred_shift = pref_raw if pref_raw in ('day', 'night') else None

                        if name:
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
                            connection.execute(text("DELETE FROM staff WHERE id = :id;"), {"id": staff_id})
                            if staff_member:
                                log_to_audit_trail("Staff Removed", f"Removed staff member: {staff_member.name} ({staff_member.role})")

                    elif action == 'set_pin':
                        staff_id = request.form.get('staff_id')
                        new_pin  = (request.form.get('new_pin') or '').strip()
                        if staff_id and new_pin and new_pin.isdigit() and len(new_pin) >= 4:
                            try:
                                pin_hash = generate_password_hash(new_pin)
                                connection.execute(text("""
                                    UPDATE staff
                                    SET pin_hash = :pin_hash,
                                        pin_set_at = NOW()
                                    WHERE id = :id;
                                """), {"pin_hash": pin_hash, "id": staff_id})
                                log_to_audit_trail("PIN Set", f"Manager set/reset PIN for staff_id={staff_id}")
                            except Exception as e:
                                print(f"ERROR setting PIN: {e}")
                        else:
                            print("WARN set_pin: invalid staff_id/new_pin")

                    elif action == 'clear_pin':
                        staff_id = request.form.get('staff_id')
                        if staff_id:
                            try:
                                connection.execute(text("""
                                    UPDATE staff
                                    SET pin_hash = NULL,
                                        pin_set_at = NULL
                                    WHERE id = :id;
                                """), {"id": staff_id})
                                log_to_audit_trail("PIN Cleared", f"Manager cleared PIN for staff_id={staff_id}")
                            except Exception as e:
                                print(f"ERROR clearing PIN: {e}")
                        else:
                            print("WARN clear_pin: missing staff_id")
        except Exception as e:
            print(f"ERROR updating staff: {e}")

        return redirect(url_for('manager_dashboard'))

    # ----- GET: fetch staff + recent audit log -----
    staff_list = []
    audit_log = []
    try:
        with engine.connect() as connection:
            staff_result = connection.execute(text("""
                SELECT id, name, role, preferred_shift, pin_set_at
                FROM staff
                ORDER BY name;
            """))
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

# --- Staff Portal (pilot PIN) -----------------------------------------------
def _infer_shift_now() -> str:
    """Return 'day' from 07:00–18:59, else 'night'."""
    now = datetime.now()
    return 'day' if time(7, 0) <= now.time() < time(19, 0) else 'night'

@app.route('/staff-portal', methods=['GET', 'POST'])
def staff_portal():
    """
    Pilot login: optional env-wide PIN (STAFF_PORTAL_PIN) + nurse name select.
    """
    pin_required = os.getenv("STAFF_PORTAL_PIN")
    prior_name = None

    if request.method == 'POST':
        entered_pin = (request.form.get('pin') or '').strip()
        staff_name  = (request.form.get('staff_name') or '').strip()
        prior_name = staff_name

        if pin_required and entered_pin != pin_required:
            flash("Invalid PIN.", "danger")
        elif not staff_name:
            flash("Please enter your name.", "danger")
        else:
            shift = _infer_shift_now()
            return redirect(url_for('staff_dashboard_for_nurse', staff_name=staff_name, shift=shift))

    nurse_names = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT name
                FROM staff
                WHERE LOWER(role) = 'nurse'
                ORDER BY name;
            """)).fetchall()
            nurse_names = [r[0] for r in rows if r[0]]
    except Exception as e:
        print(f"ERROR loading nurse names for staff portal: {e}")

    return render_template(
        'staff_portal.html',
        nurse_names=nurse_names,
        pin_required=bool(pin_required),
        prior_name=prior_name
    )

@app.route('/staff/dashboard/<staff_name>')
def staff_dashboard_for_nurse(staff_name):
    """
    Nurse dashboard:
      - scope=mine (default): only this nurse's rooms (today+shift)
      - scope=all: all active requests (to help others)
      - shift=day|night (defaults based on current time)
    """
    today = date.today()

    shift = (request.args.get('shift') or _infer_shift_now()).strip().lower()
    if shift not in ('day', 'night'):
        shift = 'day'

    scope = (request.args.get('scope') or 'mine').strip().lower()
    if scope not in ('mine', 'all'):
        scope = 'mine'

    rooms_for_nurse = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT room_number
                FROM assignments
                WHERE assignment_date = :d
                  AND shift = :s
                  AND staff_name = :n
                ORDER BY room_number;
            """), {"d": today, "s": shift, "n": staff_name}).fetchall()
            rooms_for_nurse = [r[0] for r in rows]
    except Exception as e:
        print(f"ERROR fetching rooms for nurse {staff_name}: {e}")

    active_requests = []
    try:
        with engine.connect() as connection:
            if scope == 'all':
                q = text("""
                    SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                           room, user_input, category as role, timestamp
                    FROM requests
                    WHERE completion_timestamp IS NULL
                    ORDER BY timestamp DESC;
                """)
                result = connection.execute(q)
            else:
                if rooms_for_nurse:
                    q = text("""
                        SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                               room, user_input, category as role, timestamp
                        FROM requests
                        WHERE completion_timestamp IS NULL
                          AND room = ANY(:room_list)
                        ORDER BY timestamp DESC;
                    """)
                    result = connection.execute(q, {"room_list": rooms_for_nurse})
                else:
                    result = []

            for row in result:
                active_requests.append({
                    'id': row.request_id,
                    'room': row.room,
                    'request': row.user_input,
                    'role': row.role,
                    'timestamp': row.timestamp.isoformat() if row.timestamp else None
                })
    except Exception as e:
        print(f"ERROR fetching nurse dashboard requests: {e}")

    next_scope = 'all' if scope == 'mine' else 'mine'
    toggle_url = url_for('staff_dashboard_for_nurse',
                         staff_name=staff_name, shift=shift, scope=next_scope)
    day_url   = url_for('staff_dashboard_for_nurse',
                        staff_name=staff_name, shift='day', scope=scope)
    night_url = url_for('staff_dashboard_for_nurse',
                        staff_name=staff_name, shift='night', scope=scope)

    return render_template(
        "dashboard.html",
        active_requests=active_requests,
        nurse_context=True,
        nurse_name=staff_name,
        nurse_rooms=rooms_for_nurse,
        shift=shift,
        scope=scope,
        day_url=day_url,
        night_url=night_url,
        toggle_url=toggle_url
    )

@app.get("/debug/ping_patient")
def debug_ping_patient():
    room = request.args.get("room", "").strip()
    status = request.args.get("status", "ack").strip().lower()  # ack|omw|asap
    if not _valid_room(room):
        return jsonify({"ok": False, "error": "invalid room"}), 400
    emit_patient_event("request:status", room, {
        "request_id": "debug",
        "status": status,
        "nurse": "Debug",
        "ts": datetime.now(timezone.utc).isoformat()
    })
    return jsonify({"ok": True, "room": room, "status": status})

@app.route('/api/active_requests')
def api_active_requests():
    """JSON: returns active requests for manager or for a nurse's scope."""
    today = date.today()
    staff_name = (request.args.get('staff_name') or '').strip()
    shift = (request.args.get('shift') or '').strip().lower()
    scope = (request.args.get('scope') or '').strip().lower()

    if shift not in ('day', 'night'):
        shift = None
    if scope not in ('mine', 'all'):
        scope = 'all'

    active_requests = []
    try:
        with engine.connect() as connection:
            if staff_name:
                rooms_for_nurse = []
                if shift:
                    rrows = connection.execute(text("""
                        SELECT room_number
                        FROM assignments
                        WHERE assignment_date = :d
                          AND shift = :s
                          AND staff_name = :n
                        ORDER BY room_number;
                    """), {"d": today, "s": shift, "n": staff_name}).fetchall()
                    rooms_for_nurse = [r[0] for r in rrows]

                if scope == 'mine':
                    if rooms_for_nurse:
                        res = connection.execute(text("""
                            SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                                   room, user_input, category as role, timestamp
                            FROM requests
                            WHERE completion_timestamp IS NULL
                              AND room = ANY(:room_list)
                            ORDER BY timestamp DESC;
                        """), {"room_list": rooms_for_nurse})
                    else:
                        res = []
                else:
                    res = connection.execute(text("""
                        SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                               room, user_input, category as role, timestamp
                        FROM requests
                        WHERE completion_timestamp IS NULL
                        ORDER BY timestamp DESC;
                    """))
            else:
                res = connection.execute(text("""
                    SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                           room, user_input, category as role, timestamp
                    FROM requests
                    WHERE completion_timestamp IS NULL
                    ORDER BY timestamp DESC;
                """))

            for row in res:
                active_requests.append({
                    "id": row.request_id,
                    "room": row.room,
                    "request": row.user_input,
                    "role": row.role,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None
                })
    except Exception as e:
        print(f"/api/active_requests error: {e}")
        return jsonify({"error": "fetch_failed"}), 500

    return jsonify({"active_requests": active_requests})

@app.route("/debug/assignments_today")
def debug_assignments_today():
    """Quick snapshot of today's assignments for BOTH shifts."""
    rows = []
    try:
        with engine.connect() as connection:
            res = connection.execute(text("""
                SELECT assignment_date, shift, room_number, staff_name
                FROM assignments
                WHERE assignment_date = :d
                ORDER BY shift, room_number;
            """), {"d": date.today()}).fetchall()
            rows = [dict(assignment_date=str(r[0]),
                         shift=r[1],
                         room=r[2],
                         staff=r[3]) for r in res]
    except Exception as e:
        return jsonify({"error": f"query_failed: {e.__class__.__name__}: {e}"}), 500
    return jsonify({"count": len(rows), "rows": rows})

# --- SocketIO Event Handlers -------------------------------------------------

# Patient namespace: connect first, then join via 'patient:join'
@socketio.on("connect", namespace="/patient")
def patient_connect():
    """Do not reject the connection here; some proxies race the query args."""
    try:
        room_id = (request.args.get("room_id") or "").strip()
        if _valid_room(room_id):
            join_room(f"patient:{room_id}", namespace="/patient")
            socketio.emit("patient:joined", {"room_id": room_id}, namespace="/patient")
    except Exception as e:
        print(f"[patient] connect error: {e}")

@socketio.on("patient:join", namespace="/patient")
def patient_join(data):
    """Explicit join from the client after connect/reconnect."""
    try:
        room_id = str(data.get("room_id", "")).strip()
        if _valid_room(room_id):
            join_room(f"patient:{room_id}", namespace="/patient")
            socketio.emit("patient:joined", {"room_id": room_id}, to=f"patient:{room_id}", namespace="/patient")
        else:
            socketio.emit("patient:error", {"error": "invalid_room", "room_id": room_id}, namespace="/patient")
    except Exception as e:
        print(f"[patient] join error: {e}")
        socketio.emit("patient:error", {"error": "join_exception"}, namespace="/patient")

@socketio.on("disconnect", namespace="/patient")
def patient_disconnect():
    print("[patient] client disconnected")

@socketio.on_error_default
def default_error_handler(e):
    print(f"[socketio] error: {e}")

# Generic join for dashboards/other rooms
@socketio.on("join")
def on_join(data):
    room = data.get("room")
    if room:
        join_room(room)

@socketio.on("acknowledge_request")
def handle_acknowledge(data):
    """
    Accepts both new and legacy payloads.
    """
    try:
        print("\n[acknowledge_request] IN:", data)

        dash_room = data.get("room")
        if dash_room and "message" in data:
            socketio.emit("status_update", {"message": data["message"]}, to=dash_room)

        room_number = data.get("room_number")
        if not room_number:
            reqid = data.get("request_id")
            if reqid:
                room_number = _get_room_for_request(reqid)
            if not room_number and dash_room and _valid_room(str(dash_room)):
                room_number = str(dash_room)

        status = (data.get("status") or "").lower().strip()
        if status not in ("ack", "omw", "asap"):
            msg = (data.get("message") or "").lower()
            if "ack" in msg or "received" in msg:
                status = "ack"
            elif "on my way" in msg or "on the way" in msg:
                status = "omw"
            elif "asap" in msg or "another room" in msg or "soon as" in msg:
                status = "asap"
            else:
                status = "ack"

        role = (data.get("role") or "nurse").lower().strip()
        if role not in ("nurse", "cna"):
            role = "nurse"

        print(f"[acknowledge_request] RESOLVED room={room_number} status={status} role={role}")

        if room_number and _valid_room(str(room_number)):
            payload = {
                "request_id": data.get("request_id"),
                "status": status,             # "ack" | "omw" | "asap"
                "nurse": data.get("nurse_name"),
                "role": role,                 # "nurse" | "cna"
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            print(f"[acknowledge_request] EMIT to patient:{room_number} -> request:status {payload}")
            emit_patient_event("request:status", room_number, payload)
        else:
            print(f"[acknowledge_request] SKIP emit — invalid or missing room: {room_number}")
    except Exception as e:
        print(f"[acknowledge_request] ERROR: {e}")

@socketio.on("defer_request")
def handle_defer_request(data):
    request_id = data.get("id")
    if not request_id:
        return
    now_utc = datetime.now(timezone.utc)
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(
                    text("""
                        UPDATE requests
                        SET category = 'nurse', deferral_timestamp = :now
                        WHERE request_id = :request_id;
                    """),
                    {"now": now_utc, "request_id": request_id},
                )
        socketio.emit(
            "request_updated",
            {"id": request_id, "new_role": "nurse", "new_timestamp": now_utc.isoformat()},
        )
        log_to_audit_trail("Request Deferred", f"Request ID: {request_id} deferred to NURSE.")
    except Exception as e:
        print(f"ERROR deferring request {request_id}: {e}")

@socketio.on("complete_request")
def handle_complete_request(data):
    """
    Expected data:
      - request_id (required)
      - nurse_name (optional)
      - room_number (optional; if missing, we'll look it up)
      - role (optional; 'nurse' | 'cna')
    """
    request_id = data.get("request_id")
    if not request_id:
        return

    now_utc = datetime.now(timezone.utc)
    try:
        # 1) Mark complete in DB
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(
                    text("""
                        UPDATE requests
                        SET completion_timestamp = :now
                        WHERE request_id = :request_id;
                    """),
                    {"now": now_utc, "request_id": request_id},
                )
        log_to_audit_trail("Request Completed", f"Request ID: {request_id} marked as complete.")

        # 2) Remove from dashboards
        socketio.emit("remove_request", {"id": request_id})

        # 3) Notify patient only when we have a valid room
        room_number = data.get("room_number") or _get_room_for_request(request_id)
        role = (data.get("role") or "nurse").lower().strip()
        if role not in ("nurse", "cna"):
            role = "nurse"

        if room_number and _valid_room(str(room_number)):
            emit_patient_event(
                "request:done",
                room_number,
                {
                    "request_id": request_id,
                    "status": "completed",
                    "nurse": data.get("nurse_name"),
                    "role": role,
                    "ts": now_utc.isoformat(),
                },
            )
    except Exception as e:
        print(f"ERROR updating completion timestamp: {e}")

# --- App Startup ---
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)
