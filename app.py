#triggering hard refresh please
# These two lines MUST be the very first lines in the file.
import eventlet
eventlet.monkey_patch()

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
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")


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
            with connection.begin(): # Use transaction for setup
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
def log_request_to_db(request_id, category, user_input, reply, room, is_first_baby):
    try:
        with engine.connect() as connection:
            with connection.begin(): # Use transaction for insert
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
    request_id = 'req_' + str(datetime.now().timestamp()).replace('.', '')
    room_number = session.get('room_number', 'N/A')
    is_first_baby = session.get('is_first_baby')

    socketio.start_background_task(send_email_alert, subject, user_input, room_number)
    socketio.start_background_task(log_request_to_db, request_id, role, user_input, reply_message, room_number, is_first_baby)
    
    socketio.emit('new_request', {
        'id': request_id,
        'room': room_number,
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
            reply = "I'm sorry, I didn't understand that. Please use the buttons provided."
            options = button_data["main_buttons"]

        return render_template("chat.html", reply=reply, options=options, button_data=button_data)

    return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"], button_data=button_data)

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

@app.route('/analytics')
def analytics():
    try:
        with engine.connect() as connection:
            top_requests_result = connection.execute(text("SELECT category, COUNT(id) FROM requests GROUP BY category ORDER BY COUNT(id) DESC;"))
            top_requests_data = top_requests_result.fetchall()
            top_requests_labels = [row[0] for row in top_requests_data]
            top_requests_values = [row[1] for row in top_requests_data]

            requests_by_hour_result = connection.execute(text("SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(id) FROM requests GROUP BY hour ORDER BY hour;"))
            requests_by_hour_data = requests_by_hour_result.fetchall()

            hourly_counts = defaultdict(int)
            for hour, count in requests_by_hour_data:
                hourly_counts[int(hour)] = count
            
            requests_by_hour_labels = [f"{h}:00" for h in range(24)]
            requests_by_hour_values = [hourly_counts[h] for h in range(24)]

    except Exception as e:
        print(f"ERROR fetching analytics data: {e}")
        top_requests_labels, top_requests_values = [], []
        requests_by_hour_labels, requests_by_hour_values = [], []

    return render_template('analytics.html', top_requests_labels=json.dumps(top_requests_labels), top_requests_values=json.dumps(top_requests_values), requests_by_hour_labels=json.dumps(requests_by_hour_labels), requests_by_hour_values=json.dumps(requests_by_hour_values))
    
@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    if request.method == 'POST':
        today = date.today()
        try:
            with engine.connect() as connection:
                with connection.begin():
                    for key, nurse_name in request.form.items():
                        if key.startswith('nurse_for_room_'):
                            room_number = key.replace('nurse_for_room_', '')
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
            print("Assignments saved successfully.")
        except Exception as e:
            print(f"ERROR saving assignments: {e}")
        return redirect(url_for('dashboard'))

    return render_template('assignments.html')

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
    socketio.emit('request_deferred', data)

@socketio.on('complete_request')
def handle_complete_request(data):
    request_id = data.get('request_id')
    if request_id:
        try:
            with engine.connect() as connection:
                with connection.begin(): # Start a transaction
                    connection.execute(text("""
                        UPDATE requests 
                        SET completion_timestamp = :now 
                        WHERE request_id = :request_id;
                    """), {"now": datetime.now(), "request_id": request_id})
                # The transaction is automatically committed here if no errors occurred
            
            socketio.emit('remove_request', {'id': request_id})
            
            print(f"Request {request_id} marked as complete and removal event sent.")
        except Exception as e:
            print(f"ERROR updating completion timestamp: {e}")

# --- App Startup ---
with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)

