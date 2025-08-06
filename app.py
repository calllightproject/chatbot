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
            with connection.begin():
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
        print("Database setup complete. Tables are ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

# --- Core Helper Functions ---
def log_request_to_db(request_id, category, user_input, reply):
    room = session.get("room_number", "Unknown Room")
    is_first_baby = session.get("is_first_baby", None)
    try:
        with engine.begin() as connection:
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
    except Exception as e:
        print(f"ERROR logging to database: {e}")

def send_email_alert(subject, body):
    # This function remains the same
    pass

def process_request(role, subject, user_input, reply_message):
    request_id = 'req_' + str(datetime.now().timestamp()).replace('.', '')
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
        return f"Error: Configuration file '{config_module_name}.py' is missing or invalid."

    if request.method == 'POST':
        user_input = request.form.get("user_input", "").strip()
        
        if request.form.get("action") == "send_note":
            note_text = request.form.get("custom_note")
            if note_text:
                reply = process_request(role="nurse", subject="Custom Patient Note", user_input=note_text, reply_message=button_data["nurse_notification"])
            else:
                reply = "Please type a message in the box."
            return render_template("chat.html", reply=reply, options=button_data["main_buttons"], button_data=button_data)
        
        if user_input == button_data.get("back_text", "⬅ Back"):
            return redirect(url_for('handle_chat'))

        if user_input in button_data:
            button_info = button_data[user_input]
            reply = button_info.get("question") or button_info.get("note", "")
            options = button_info.get("options", [])
            
            back_text = button_data.get("back_text", "⬅ Back")
            if options and back_text not in options:
                options.append(back_text)
            elif not options:
                options = button_data["main_buttons"]

            if "action" in button_info:
                action = button_info["action"]
                role = "cna" if action == "Notify CNA" else "nurse"
                subject = f"{role.upper()} Request"
                notification_message = button_info.get("note", button_data[f"{role}_notification"])
                reply = process_request(role=role, subject=subject, user_input=user_input, reply_message=notification_message)
                options = button_data["main_buttons"]
        else:
            reply = "I'm sorry, I didn't understand that."
            options = button_data["main_buttons"]

        return render_template("chat.html", reply=reply, options=options, button_data=button_data)

    return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"], button_data=button_data)

@app.route("/reset-language")
def reset_language():
    session.clear()
    return redirect(url_for("language_selector"))

@app.route("/dashboard")
def dashboard():
    active_requests_by_room = defaultdict(list)
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT request_id, room, user_input, category as role, timestamp
                FROM requests 
                WHERE completion_timestamp IS NULL 
                ORDER BY room, timestamp ASC;
            """))
            for row in result:
                active_requests_by_room[row.room].append({
                    'id': row.request_id,
                    'request': row.user_input,
                    'role': row.role,
                    'timestamp': row.timestamp.isoformat()
                })
    except Exception as e:
        print(f"ERROR fetching active requests: {e}")
    
    return render_template("dashboard.html", active_requests_by_room=active_requests_by_room)

@app.route('/analytics')
def analytics():
    # This function remains the same
    pass

@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    # This function remains the same
    pass

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
    socketio.emit('request_deferred', data)

@socketio.on('complete_request')
def handle_complete_request(data):
    request_id = data.get('request_id')
    if request_id:
        try:
            with engine.begin() as connection:
                connection.execute(text("""
                    UPDATE requests 
                    SET completion_timestamp = :now 
                    WHERE request_id = :request_id;
                """), {"now": datetime.now(), "request_id": request_id})
        except Exception as e:
            print(f"ERROR updating completion timestamp: {e}")

with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)
