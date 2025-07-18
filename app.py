import os
import json
import smtplib
import importlib
from datetime import datetime
from collections import defaultdict
from email.message import EmailMessage

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO
from sqlalchemy import create_engine, text

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")
socketio = SocketIO(app)

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
                    timestamp TIMESTAMP WITHOUT TIME ZONE,
                    room VARCHAR(255),
                    user_input TEXT,
                    category VARCHAR(255),
                    reply TEXT
                );
            """))
            connection.commit()
            try:
                connection.execute(text("ALTER TABLE requests ADD COLUMN completion_timestamp TIMESTAMP WITHOUT TIME ZONE;"))
                connection.commit()
                print("SUCCESS: Added 'completion_timestamp' column.")
            except Exception:
                print("INFO: 'completion_timestamp' column already exists.")
        print("Database setup complete.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

# --- Core Helper Functions ---
def log_request_to_db(category, user_input, reply):
    room = session.get("room_number", "Unknown Room")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                INSERT INTO requests (timestamp, room, category, user_input, reply)
                VALUES (:timestamp, :room, :category, :user_input, :reply) RETURNING id;
            """), {
                "timestamp": datetime.now(), "room": room, "category": category,
                "user_input": user_input, "reply": reply
            })
            new_id = result.fetchone()[0]
            connection.commit()
            return new_id
    except Exception as e:
        print(f"ERROR logging to database: {e}")
        return None

def send_email_alert(subject, body):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
    if not sender_email or not sender_password:
        print("WARNING: Email credentials not set.")
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
    request_id = log_request_to_db(role, user_input, reply_message)
    socketio.emit('new_request', {
        'id': request_id, 'room': session.get('room_number', 'N/A'),
        'request': user_input, 'role': role
    })
    send_email_alert(subject, user_input)
    return reply_message

# --- Pathway and Language Setup Routes ---
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
        language_choice = request.form.get("language")
        session["language"] = language_choice
        # --- NEW DEBUGGING LINE ---
        print(f"--- Language SET in session: {language_choice} ---")
        return redirect(url_for("handle_chat"))
    return render_template("language.html")

# --- REFACTORED: Unified Chatbot Route ---
@app.route("/chat", methods=["GET", "POST"])
def handle_chat():
    # --- NEW DEBUGGING LINE ---
    retrieved_lang = session.get("language")
    print(f"--- Language READ from session: {retrieved_lang} ---")
    
    lang = session.get("language", "en")
    pathway = session.get("pathway", "standard")
    
    config_module_name = f"button_config_bereavement_{lang}" if pathway == "bereavement" else f"button_config_{lang}"
    
    try:
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data
    except (ImportError, AttributeError) as e:
        print(f"ERROR: Could not load config '{config_module_name}'. Falling back to English. Error: {e}")
        lang = "en"
        config_module_name = f"button_config_bereavement_{lang}" if pathway == "bereavement" else f"button_config_{lang}"
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data

    if request.method == "GET" or 'user_input' not in request.form:
        return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"], button_data=button_data)

    user_input = request.form.get("user_input", "").strip()
    
    if request.form.get("action") == "send_note":
        note_text = request.form.get("custom_note")
        reply = process_request("nurse", "Custom Patient Note", note_text, button_data["nurse_notification"]) if note_text else "Please type a message in the box."
        return render_template("chat.html", reply=reply, options=button_data["main_buttons"], button_data=button_data)

    if user_input == button_data.get("back_text", "⬅ Back"):
        return redirect(url_for('handle_chat'))

    if user_input in button_data:
        button_info = button_data[user_input]
        reply = button_info.get("question") or button_info.get("note", "")
        options = button_info.get("options", [])
        
        if options:
            options.append(button_data.get("back_text", "⬅ Back"))
        else:
            options = button_data["main_buttons"]

        if "action" in button_info:
            action = button_info["action"]
            role = "cna" if action == "Notify CNA" else "nurse"
            subject = f"{role.upper()} Request"
            reply = process_request(role, subject, user_input, button_data[f"{role}_notification"])
            options = button_data["main_buttons"]
    else:
        reply = "I'm sorry, I didn't understand that. Please use the buttons provided."
        options = button_data["main_buttons"]

    return render_template("chat.html", reply=reply, options=options, button_data=button_data)

@app.route("/reset-language")
def reset_language():
    session.pop("language", None)
    return redirect(url_for("language_selector"))

# --- Staff-Facing Routes ---
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route('/analytics')
def analytics():
    try:
        with engine.connect() as connection:
            # ... (analytics queries) ...
            pass
    except Exception as e:
        print(f"ERROR fetching analytics data: {e}")
    return render_template('analytics.html', top_requests_labels='[]', top_requests_values='[]', requests_by_hour_labels='[]', requests_by_hour_values='[]')

# --- SocketIO Event Handlers ---
@socketio.on('defer_request')
def handle_defer_request(data):
    socketio.emit('request_deferred', data)

@socketio.on('mark_complete')
def handle_mark_complete(data):
    request_id = data.get('id')
    if request_id:
        try:
            with engine.connect() as connection:
                connection.execute(text("UPDATE requests SET completion_timestamp = :now WHERE id = :id;"), {"now": datetime.now(), "id": request_id})
                connection.commit()
                print(f"Request {request_id} marked as complete.")
        except Exception as e:
            print(f"Error updating request {request_id}: {e}")

# --- App Startup ---
with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)
