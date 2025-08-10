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

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, join_room
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")

# --- FINAL FIX: This more explicit configuration is more robust for hosting providers ---
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*", manage_session=False)


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
                        timestamp TIMESTAMP WITHOUT TIME ZONE,
                        completion_timestamp TIMESTAMP WITHOUT TIME ZONE,
                        deferral_timestamp TIMESTAMP WITHOUT TIME ZONE,
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
                        room_number VARCHAR(255) NOT NULL,
                        nurse_name VARCHAR(255) NOT NULL,
                        UNIQUE(assignment_date, room_number)
                    );
                """))
                try:
                    connection.execute(text("""
                        ALTER TABLE requests ADD COLUMN deferral_timestamp TIMESTAMP WITHOUT TIME ZONE;
                    """))
                    print("SUCCESS: Added 'deferral_timestamp' column to requests table.")
                except ProgrammingError:
                    print("INFO: 'deferral_timestamp' column likely already exists. Continuing.")
                    pass
        print("Database setup complete. Tables are ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

# --- Core Helper Functions (no changes here) ---
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
    except Exception as e:
        print(f"ERROR logging to database: {e}")

def send_email_alert(subject, body, room_number):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
    if not sender_email or not sender_password:
        print("WARNING: Email credentials not set. Cannot send email.")
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
    request_id = 'req_' + str(datetime.now(timezone.utc).timestamp()).replace('.', '')
    room_number = session.get('room_number', 'N/A')
    is_first_baby = session.get('is_first_baby')
    socketio.start_background_task(send_email_alert, subject, user_input, room_number)
    socketio.start_background_task(log_request_to_db, request_id, role, user_input, reply_message, room_number, is_first_baby)
    socketio.emit('new_request', {
        'id': request_id, 'room': room_number, 'request': user_input,
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
                reply = process_request(role="nurse", subject="Custom Patient Note", user_input=note_text, reply_message=button_data["nurse_notification"])
            else:
                reply = "Please type a message in the box."
            return render_template("chat.html", reply=reply, options=button_data["main_buttons"], button_data=button_data)
        user_input = request.form.get("user_input", "").strip()
        if user_input == button_data.get("back_text", "⬅ Back"):
            return redirect(url_for('handle_chat'))
        if user_input in button_data:
            button_info = button_data[user_input]
            reply = button_info.get("question") or button_info.get("note", "")
            options = button_info.get("options", [])
            back_text = but
