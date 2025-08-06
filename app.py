import os
import json
import smtplib
import importlib
from datetime import datetime, date
from collections import defaultdict
from email.message import EmailMessage

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, join_room
from sqlalchemy import create_engine, text

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")
socketio = SocketIO(app, async_mode='threading')  # Explicitly specify async_mode to avoid eventlet issues

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("WARNING: DATABASE_URL environment variable not found. Using a local SQLite database.")
    DATABASE_URL = "sqlite:///local_call_light.db"

engine = create_engine(DATABASE_URL)

# --- Database Setup ---
def setup_database():
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS requests (
                    id SERIAL PRIMARY KEY,
                    request_id VARCHAR(255) UNIQUE,
                    timestamp TIMESTAMP WITHOUT TIME ZONE,
                    completion_timestamp TIMESTAMP WITHOUT TIME ZONE,
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
            connection.commit()
        print("Database setup complete. Tables are ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

# --- Helper Functions ---
def determine_role_from_note(note_text):
    cna_keywords = ["diaper", "wipes", "ice", "blanket", "water", "peri bottle", "socks"]
    for word in cna_keywords:
        if word.lower() in note_text.lower():
            return "cna"
    return "nurse"

def log_request_to_db(request_id, category, user_input, reply):
    room = session.get("room_number", "Unknown Room")
    is_first_baby = session.get("is_first_baby", None)
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                INSERT INTO requests (request_id, timestamp, room, category, user_input, reply, is_first_baby)
                VALUES (:request_id, :timestamp, :room, :category, :user_input, :reply, :is_first_baby);
            """), {
                "request_id": request_id,
                "timestamp": datetime.now(),
                "room": room,
                "category": category,
                "user_input": user_input,
                "reply": reply,
                "is_first_baby": is_first_baby
            })
            connection.commit()
    except Exception as e:
        print(f"ERROR logging to database: {e}")

def send_email_alert(subject, body):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
    if not sender_email or not sender_password:
        print("WARNING: Email credentials not set. Cannot send email.")
        return
    msg = EmailMessage()
    msg["Subject"] = f"Room {session.get('room_number', 'N/A')} - {subject}"
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
    request_id = 'req_' + str(datetime.now().timestamp()).replace('.', '')
    try:
        send_email_alert(subject, user_input)
        log_request_to_db(request_id, role, user_input, reply_message)
        socketio.emit('new_request', {
            'id': request_id,
            'room': session.get('room_number', 'N/A'),
            'request': user_input,
            'role': role,
            'timestamp': datetime.now().isoformat()
        })
        return reply_message
    except Exception as e:
        print(f"ERROR in process_request: {e}")
        return "Something went wrong. Please try again."

# --- Chat Route Updates ---
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
                role = determine_role_from_note(note_text)
                reply = process_request(role=role, subject="Custom Patient Note", user_input=note_text, reply_message=button_data[f"{role}_notification"])
            else:
                reply = "Please type a message in the box."
            return render_template("chat.html", reply=reply, options=button_data["main_buttons"], button_data=button_data)

    # No change to rest of the route logic
    # ... (keep existing logic unchanged)

    return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"], button_data=button_data)

# --- Dashboard Timestamp Update ---
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
                    'timestamp': row.timestamp.strftime("%Y-%m-%dT%H:%M:%S")
                })
    except Exception as e:
        print(f"ERROR fetching active requests: {e}")

    return render_template("dashboard.html", active_requests=json.dumps(active_requests))

# --- Startup ---
with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)
