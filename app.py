import eventlet
# Patch must happen before other imports, specifically socket/threading
eventlet.monkey_patch()

import os
import json
import smtplib
import importlib
import hmac
import hashlib
from datetime import timedelta, datetime, date, time, timezone
from collections import defaultdict
from email.message import EmailMessage

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, abort
from flask_socketio import SocketIO, join_room
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from werkzeug.security import generate_password_hash, check_password_hash

# Ensure triage_engine.py exists in the same directory
try:
    from triage_engine import TriageEngine
except ImportError:
    print("WARNING: triage_engine module not found. The app will fail if TriageEngine is required.")
    class TriageEngine: 
        def classify(self, text): pass # Placeholder

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")

# Define the rooms based on your DB logic (231-260)
ALL_ROOMS = [str(r) for r in range(231, 261)]

# Initialize the Triage Engine here
try:
    triage = TriageEngine()
except Exception as e:
    print(f"Error initializing TriageEngine: {e}")
    triage = None

socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    manage_session=False,
    ping_timeout=60,
    ping_interval=25
)

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

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

                # --- Rooms Registry (Banner-ready foundation) ---
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS rooms (
                        room_number VARCHAR(20) PRIMARY KEY,
                        unit VARCHAR(64),
                        is_active BOOLEAN NOT NULL DEFAULT FALSE,
                        activated_by VARCHAR(128),
                        activated_at TIMESTAMPTZ,
                        expires_at TIMESTAMPTZ,
                        banner_location_id VARCHAR(64),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """))

                # Hardening for older DBs
                try:
                    connection.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS unit VARCHAR(64);"))
                    connection.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE;"))
                    connection.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS activated_by VARCHAR(128);"))
                    connection.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;"))
                    connection.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;"))
                    connection.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS banner_location_id VARCHAR(64);"))
                    connection.execute(text("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();"))
                except Exception as e:
                    print(f"WARN: rooms hardening skipped/failed (non-fatal): {e}")

                # Seed default rooms (exists-only; starts INACTIVE by default)
                # Using SQLite syntax compat or standard SQL
                try:
                    room_count = connection.execute(text("SELECT COUNT(*) FROM rooms")).scalar()
                    if room_count == 0:
                        print("Seeding default rooms 231-260 into database...")
                        for r in range(231, 261):
                            connection.execute(text("""
                                INSERT INTO rooms (room_number, unit, is_active)
                                VALUES (:r, :unit, FALSE)
                            """), {"r": str(r), "unit": "Postpartum"})
                except Exception as e:
                    print(f"WARN: Could not seed rooms: {e}")

                print("CREATE TABLE statements complete.")

    except Exception as e:
        print(f"Database setup error: {e}")

def migrate_schema():
    try:
        with engine.connect() as connection:
            with connection.begin():
                # staff.preferred_shift
                connection.execute(text("""
                    ALTER TABLE staff
                    ADD COLUMN IF NOT EXISTS preferred_shift VARCHAR(10);
                """))

                # assignments.shift
                connection.execute(text("""
                    ALTER TABLE assignments
                    ADD COLUMN IF NOT EXISTS shift VARCHAR(10);
                """))
                
                # Check for cna_coverage existence again to be safe or alter columns
                print("Schema migration checks complete.")
    except Exception as e:
        print(f"Schema migration error: {e}")

# --- Localized label -> English maps for structured buttons ---
ES_TO_EN = {
    "Tengo una emergencia": "I'm having an emergency",
    "Necesito suministros": "I need supplies",
    # ... (Truncated map for brevity, logic remains valid) ...
}
ZH_TO_EN = {
    "我有紧急情况": "I'm having an emergency",
    # ... (Truncated map for brevity) ...
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

def send_email_alert(subject, body, room_number):
    """Safe/no-op email alert. Will quietly skip if creds arent set."""
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
        # Normalize room for storage + debugging
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

def process_request(role, subject, user_input, reply_message, tier_override=None, classify_from_text=True, from_button=False):
    lang = session.get("language", "en")
    english_user_input = to_english_label(user_input, lang)
    request_id = "req_" + str(datetime.now(timezone.utc).timestamp()).replace(".", "")

    room_number = _current_room() or session.get("room_number")
    if not room_number or not _valid_room(room_number):
        room_number = None 

    is_first_baby = session.get("is_first_baby")

    if tier_override is not None:
        tier = tier_override
    elif classify_from_text and triage:
        classification = triage.classify(english_user_input)
        tier = classification.tier.value.lower()
    else:
        tier = "routine"

    socketio.start_background_task(
        log_request_to_db,
        request_id, role, english_user_input, reply_message, room_number, is_first_baby,
    )

    socketio.emit(
        "new_request",
        {
            "id": request_id,
            "room": room_number,
            "request": english_user_input,
            "role": role,
            "tier": tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
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

# ---- helpers for this block ----
def _valid_room(room_str: str) -> bool:
    if not room_str or not str(room_str).isdigit():
        return False
    n = int(room_str)
    return 231 <= n <= 260

def _current_room() -> str | None:
    room = request.args.get("room") or session.get("room_number")
    if room and _valid_room(str(room)):
        room_str = str(room)
        if session.get("room_number") != room_str:
            session["room_number"] = room_str
        return room_str
    return None

def _emit_received_for(room_number: str, user_text: str, kind: str):
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

# --- Security Helpers ---
def _qr_secret() -> str:
    secret = os.getenv("ROOM_QR_SECRET", "")
    if not secret:
        # Avoid crashing in dev if not set, but warn
        print("WARN: ROOM_QR_SECRET not set.")
        return "dev-secret"
    return secret

def sign_room(room_number: str) -> str:
    msg = str(room_number).strip().encode("utf-8")
    key = _qr_secret().encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def verify_room_sig(room_number: str, sig: str) -> bool:
    if not room_number or not sig:
        return False
    expected = sign_room(room_number)
    return hmac.compare_digest(expected, sig)

@app.route("/chat", methods=["GET", "POST"])
def handle_chat():
    qp = (request.args.get("pathway") or "").strip().lower()
    if qp in ("standard", "bereavement"):
        session["pathway"] = qp

    pathway = session.get("pathway", "standard")
    lang = session.get("language", "en")

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
        return f"Error loading config for {lang}. Please contact support."

    room_number = _current_room()
    room_from_form = (request.form.get("room") or "").strip() if request.method == "POST" else ""
    if room_from_form and _valid_room(room_from_form):
        session["room_number"] = room_from_form
        room_number = room_from_form

    if request.method == "POST":
        if request.form.get("action") == "send_note":
            note_text = (request.form.get("custom_note") or "").strip()
            if note_text:
                classification = triage.classify(note_text) if triage else None
                role = classification.routing.value.lower() if classification else "nurse"
                tier = classification.tier.value.lower() if classification else "routine"
                
                reply_message = button_data.get(f"{role}_notification", "Your request has been sent.")
                
                session["reply"] = process_request(
                    role=role,
                    subject="Custom Patient Note",
                    user_input=note_text,
                    reply_message=reply_message,
                    tier_override=tier,
                    classify_from_text=False,
                    from_button=False,
                )
                session["options"] = button_data["main_buttons"]
                if room_number:
                    _emit_received_for(room_number, note_text, kind="note")
            else:
                session["reply"] = button_data.get("empty_custom_note", "Please type a message in the box.")
                session["options"] = button_data["main_buttons"]
        else:
            user_input = (request.form.get("user_input") or "").strip()
            back_text = button_data.get("back_text", "⬅ Back")

            if user_input == "I'm having an emergency":
                request_text = "Patient pressed EMERGENCY button: 'I'm having an emergency'."
                session["reply"] = process_request(
                    role="nurse",
                    subject="EMERGENCY – patient pressed emergency button",
                    user_input=request_text,
                    reply_message=button_data.get("nurse_notification", "Your nurse has been notified."),
                    tier_override="emergent",
                    classify_from_text=False,
                    from_button=True,
                )
                session["options"] = button_data["main_buttons"]
                if room_number:
                    _emit_received_for(room_number, request_text, kind="option")

            elif user_input == "Can I take a shower?":
                session["reply"] = "Usually yes — but please check with your nurse if you have an IV, had a C-section, or have special instructions."
                session["options"] = [
                    "Ask my nurse about taking a shower",
                    "Got it, I'll wait for now",
                ]
                if back_text not in session["options"]:
                    session["options"].append(back_text)

            elif user_input == "Ask my nurse about taking a shower":
                request_text = "Patient would like to ask about taking a shower."
                session["reply"] = process_request(
                    role="nurse",
                    subject="Shower permission request",
                    user_input=request_text,
                    reply_message=button_data.get("nurse_notification", "Your request has been sent."),
                    tier_override=None,
                    classify_from_text=False,
                    from_button=True,
                )
                session["options"] = button_data["main_buttons"]
                if room_number:
                    _emit_received_for(room_number, request_text, kind="option")

            elif user_input == "Got it, I'll wait for now":
                session["reply"] = "Okay — if you change your mind, just let me know anytime."
                session["options"] = button_data["main_buttons"]

            elif user_input == back_text:
                session.pop("reply", None)
                session.pop("options", None)
                return redirect(url_for("handle_chat", room=room_number) if room_number else url_for("handle_chat"))

            elif user_input in button_data:
                button_info = button_data[user_input]
                session["reply"] = button_info.get("question") or button_info.get("note", "")
                session["options"] = button_info.get("options", [])
                if session["options"] and back_text not in session["options"]:
                    session["options"].append(back_text)
                elif not session["options"]:
                    session["options"] = button_data["main_buttons"]

                if "action" in button_info:
                    action = button_info["action"]
                    role = "cna" if action == "Notify CNA" else "nurse"
                    subject = f"{role.upper()} Request"
                    notification_message = button_info.get(
                        "note",
                        button_data.get(f"{role}_notification", "Your request has been sent.")
                    )
                    session["reply"] = process_request(
                        role=role,
                        subject=subject,
                        user_input=user_input,
                        reply_message=notification_message,
                        tier_override=None,
                        classify_from_text=False,
                        from_button=True,
                    )
                    session["options"] = button_data["main_buttons"]
                    if room_number:
                        _emit_received_for(room_number, user_input, kind="option")
            else:
                session["reply"] = button_data.get(
                    "fallback_unrecognized",
                    "I'm sorry, I didn't understand that. Please use the buttons provided.",
                )
                session["options"] = button_data["main_buttons"]

        return redirect(url_for("handle_chat", room=room_number) if room_number else url_for("handle_chat"))

    reply = session.pop("reply", button_data["greeting"])
    options = session.pop("options", button_data["main_buttons"])
    return render_template(
        "chat.html",
        reply=reply,
        options=options,
        button_data=button_data,
        room_number=room_number,
    )

@app.route("/reset-language")
def reset_language():
    session.pop("language", None)
    session.pop("is_first_baby", None)
    session.pop("reply", None)
    session.pop("options", None)
    return redirect(url_for("language_selector"))

@app.route("/dashboard")
def dashboard():
    active_requests = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT
                    COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                    room, user_input, category AS role, timestamp
                FROM requests
                WHERE completion_timestamp IS NULL
                ORDER BY timestamp DESC;
            """))

            for row in result:
                text_for_tier = (row.user_input or "").strip()
                tier = "routine"
                if "patient pressed emergency button" in text_for_tier.lower():
                    tier = "emergent"
                elif triage:
                    classification = triage.classify(text_for_tier)
                    tier = classification.tier.value.lower()
                
                active_requests.append({
                    "id": row.request_id,
                    "room": row.room,
                    "request": row.user_input,
                    "role": row.role,
                    "tier": tier,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                })
    except Exception as e:
        print(f"ERROR fetching active requests: {e}")
    return render_template("dashboard.html", active_requests=active_requests, nurse_context=False)

@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    today = date.today()
    shift = (request.args.get('shift') or request.form.get('shift') or 'day').lower()
    if shift not in ('day', 'night'):
        shift = 'day'

    preferred_nurses, other_nurses, opposite_nurses = [], [], []
    all_cnas = []
    
    # Load Staff
    try:
        with engine.connect() as connection:
            # Nurses
            rows = connection.execute(text("SELECT name, preferred_shift FROM staff WHERE LOWER(role)='nurse' ORDER BY name")).fetchall()
            for r in rows:
                name = r[0]
                pref = (r[1] or 'unspecified').lower().strip()
                if pref == shift: preferred_nurses.append(name)
                elif pref in ('day', 'night'): opposite_nurses.append(name)
                else: other_nurses.append(name)
            
            # CNAs
            cna_rows = connection.execute(text("SELECT name FROM staff WHERE LOWER(role)='cna' ORDER BY name")).fetchall()
            all_cnas = [r[0] for r in cna_rows]
    except Exception as e:
        print(f"Error loading staff: {e}")

    if request.method == 'POST':
        try:
            with engine.connect() as connection:
                with connection.begin():
                    # Save Nurse Assignments
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
                                DELETE FROM assignments WHERE assignment_date=:d AND shift=:s AND room_number=:r
                            """), {"d": today, "s": shift, "r": room_number})
                    
                    # Save CNA Coverage
                    cna_front = request.form.get('cna_front')
                    cna_back = request.form.get('cna_back')
                    for zone, name in [('front', cna_front), ('back', cna_back)]:
                        if name and name != 'unassigned':
                            connection.execute(text("""
                                INSERT INTO cna_coverage (assignment_date, shift, zone, cna_name)
                                VALUES (:d, :s, :z, :n)
                                ON CONFLICT (assignment_date, shift, zone) DO UPDATE SET cna_name = EXCLUDED.cna_name
                            """), {"d": today, "s": shift, "z": zone, "n": name})
                        else:
                            connection.execute(text("DELETE FROM cna_coverage WHERE assignment_date=:d AND shift=:s AND zone=:z"),
                                               {"d": today, "s": shift, "z": zone})

            return redirect(url_for('assignments', shift=shift))
        except Exception as e:
            print(f"Error saving assignments: {e}")

    # Read existing
    current_assignments = {}
    cna_front, cna_back = 'unassigned', 'unassigned'
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT room_number, staff_name FROM assignments WHERE assignment_date=:d AND shift=:s"),
                                      {"d": today, "s": shift}).fetchall()
            for r in rows:
                current_assignments[r.room_number] = r.staff_name
            
            crows = connection.execute(text("SELECT zone, cna_name FROM cna_coverage WHERE assignment_date=:d AND shift=:s"),
                                       {"d": today, "s": shift}).fetchall()
            for r in crows:
                if r.zone == 'front': cna_front = r.cna_name
                if r.zone == 'back': cna_back = r.cna_name
    except Exception as e:
        print(f"Error reading assignments: {e}")

    return render_template(
        'assignments.html',
        all_rooms=ALL_ROOMS,
        preferred_nurses=preferred_nurses,
        other_nurses=other_nurses,
        opposite_nurses=opposite_nurses,
        current_assignments=current_assignments,
        all_cnas=all_cnas,
        cna_front=cna_front,
        cna_back=cna_back,
        shift=shift
    )

@app.route('/room/reset', methods=['POST'])
def room_reset():
    today = date.today()
    shift = (request.form.get('shift') or 'day').lower()
    room = (request.form.get('room') or '').strip()
    if not room: return redirect(url_for('assignments', shift=shift))

    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    INSERT INTO room_state (assignment_date, shift, room_number, reset_at, tags)
                    VALUES (:d, :s, :r, NOW(), COALESCE((SELECT tags FROM room_state WHERE assignment_date=:d AND shift=:s AND room_number=:r), '[]'))
                    ON CONFLICT (assignment_date, shift, room_number) DO UPDATE SET reset_at = EXCLUDED.reset_at
                """), {"d": today, "s": shift, "r": room})
                
                connection.execute(text("DELETE FROM assignments WHERE assignment_date=:d AND shift=:s AND room_number=:r"),
                                   {"d": today, "s": shift, "r": room})
    except Exception as e:
        print(f"Error resetting room: {e}")
    return redirect(url_for('assignments', shift=shift))

# --- SocketIO Event Handlers ---
def emit_patient_event(event: str, room_number: str | int, payload: dict):
    socketio.emit(event, {"room_id": str(room_number), **(payload or {})}, to=f"patient:{room_number}", namespace="/patient")

@socketio.on("connect", namespace="/patient")
def patient_connect():
    pass # Wait for explicit join

@socketio.on("patient:join", namespace="/patient")
def patient_join(data):
    room_id = str(data.get("room_id", "")).strip()
    if _valid_room(room_id):
        join_room(f"patient:{room_id}", namespace="/patient")
        socketio.emit("patient:joined", {"room_id": room_id}, to=f"patient:{room_id}", namespace="/patient")
    else:
        socketio.emit("patient:error", {"error": "invalid_room"}, namespace="/patient")

@socketio.on("join")
def on_join(data):
    if data.get("room"): join_room(data["room"])

@socketio.on("acknowledge_request")
def handle_acknowledge(data):
    try:
        if data.get("room") and "message" in data:
             socketio.emit("status_update", {"message": data["message"]}, to=data["room"])
        
        room_number = data.get("room_number")
        if room_number and _valid_room(str(room_number)):
            status = data.get("status", "ack").lower()
            emit_patient_event("request:status", room_number, {
                "request_id": data.get("request_id"),
                "status": status,
                "nurse": data.get("nurse_name"),
                "role": data.get("role", "nurse"),
                "ts": datetime.now(timezone.utc).isoformat()
            })
    except Exception as e:
        print(f"Error acknowledge: {e}")

@socketio.on("complete_request")
def handle_complete_request(data):
    req_id = data.get("request_id")
    if not req_id: return
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("UPDATE requests SET completion_timestamp=:now WHERE request_id=:id"),
                                   {"now": datetime.now(timezone.utc), "id": req_id})
        socketio.emit("remove_request", {"id": req_id})
        
        # Notify patient if room is known
        room_number = data.get("room_number")
        if room_number and _valid_room(str(room_number)):
             emit_patient_event("request:done", room_number, {"request_id": req_id, "status": "completed"})
    except Exception as e:
        print(f"Error complete_request: {e}")

# --- Startup ---
if __name__ == "__main__":
    setup_database()
    migrate_schema()
    port = int(os.getenv('PORT', 5000))
    print(f"Starting server on port {port}...")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)
