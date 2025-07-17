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
# IMPORTANT: For production, generate a truly random secret key.
# You can use: import secrets; secrets.token_hex(16)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-fallback-secret-key-for-local-dev")
socketio = SocketIO(app)

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("WARNING: DATABASE_URL environment variable not found. Using a local SQLite database.")
    DATABASE_URL = "sqlite:///local_call_light.db"

# Create a single, reusable database engine
engine = create_engine(DATABASE_URL)

# --- Database Setup ---
def setup_database():
    """Creates the 'requests' table in the database if it doesn't already exist."""
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
        print("Database setup complete. 'requests' table is ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

# --- Helper Functions ---
def log_request(category, user_input, reply):
    """Logs a request to the PostgreSQL database."""
    room = session.get("room_number", "Unknown Room")
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                INSERT INTO requests (timestamp, room, category, user_input, reply)
                VALUES (:timestamp, :room, :category, :user_input, :reply);
            """), {
                "timestamp": datetime.now(),
                "room": room,
                "category": category,
                "user_input": user_input,
                "reply": reply
            })
            connection.commit()
    except Exception as e:
        print(f"ERROR logging to database: {e}")

def send_email_alert(subject, body):
    """Sends an email alert for a new request."""
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")

    if not sender_email or not sender_password:
        print("WARNING: Email credentials (EMAIL_USER, EMAIL_PASSWORD) not set. Cannot send email.")
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

def notify_and_log(role, subject, user_input, reply_message):
    """A central function to handle logging, emailing, and socket emissions for a request."""
    send_email_alert(subject, user_input)
    log_request(role, user_input, reply_message)
    socketio.emit('new_request', {
        'room': session.get('room_number', 'N/A'),
        'request': user_input,
        'role': role
    })
    return reply_message

# --- Main Application Routes ---
@app.route("/room/<room_id>")
def set_room(room_id):
    """Sets the room number and standard pathway in the session."""
    session.clear()
    session["room_number"] = room_id
    session["pathway"] = "standard"
    return redirect(url_for("language_selector"))

@app.route("/bereavement/<room_id>")
def set_bereavement_room(room_id):
    """Sets the room number and bereavement pathway in the session."""
    session.clear()
    session["room_number"] = room_id
    session["pathway"] = "bereavement"
    return redirect(url_for("language_selector"))

@app.route("/", methods=["GET", "POST"])
def language_selector():
    """Displays the language selection page and redirects to the correct chatbot."""
    if request.method == "POST":
        session["language"] = request.form.get("language")
        pathway = session.get("pathway", "standard")
        if pathway == "bereavement":
            return redirect(url_for("bereavement_chatbot"))
        else:
            return redirect(url_for("chatbot"))
    return render_template("language.html")

@app.route("/chat", methods=["GET", "POST"])
def chatbot():
    """Handles the main chatbot logic for standard patient requests."""
    if session.get("pathway") != "standard":
        return redirect(url_for("language_selector"))

    lang = session.get("language", "en")
    try:
        button_config = importlib.import_module(f"button_config_{lang}")
        button_data = button_config.button_data
    except (ImportError, AttributeError):
        # Fallback if a language config file is missing or broken
        return "Error: Language configuration file is missing or invalid. Please contact support."


    if request.method == "GET":
        return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"], button_data=button_data)

    # Handle all POST requests (button clicks, form submissions)
    user_input = request.form.get("user_input", "").strip()
    
    # Handle custom note submission
    if request.form.get("action") == "send_note":
        note_text = request.form.get("custom_note")
        reply = notify_and_log("nurse", "Custom Patient Note", note_text, button_data["nurse_notification"]) if note_text else "Please type a message in the box."
        return render_template("chat.html", reply=reply, options=button_data["main_buttons"], button_data=button_data)

    # Handle back button
    if user_input == button_data.get("back_text", "⬅ Back"):
        return redirect(url_for('chatbot'))

    # Process button clicks from config file
    if user_input in button_data:
        button_info = button_data[user_input]
        reply = button_info.get("question") or button_info.get("note", "")
        options = button_info.get("options", [])
        
        if options: # If there are sub-options, add a back button
             options.append(button_data.get("back_text", "⬅ Back"))
        else: # Otherwise, it's a main action, so show main buttons
            options = button_data["main_buttons"]

        if "action" in button_info:
            action = button_info["action"]
            role = "cna" if action == "Notify CNA" else "nurse"
            subject = f"{role.upper()} Request"
            notification_text = reply or button_data[f"{role}_notification"]
            reply = notify_and_log(role, subject, user_input, notification_text)
            options = button_data["main_buttons"] # After action, return to main menu
    else:
        # Fallback for unexpected inputs (e.g., if user tries to type something)
        reply = "I'm sorry, I didn't understand that. Please use the buttons provided."
        options = button_data["main_buttons"]

    return render_template("chat.html", reply=reply, options=options, button_data=button_data)


@app.route("/bereavement-chat", methods=["GET", "POST"])
def bereavement_chatbot():
    """Handles the separate chatbot logic for bereavement support."""
    if session.get("pathway") != "bereavement":
        return redirect(url_for("language_selector"))

    lang = session.get("language", "en")
    try:
        button_config = importlib.import_module(f"button_config_bereavement_{lang}")
        button_data = button_config.button_data
    except (ImportError, AttributeError):
        return "Error: Bereavement language configuration file is missing or invalid."

    if request.method == "GET":
        return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"], button_data=button_data)

    user_input = request.form.get("user_input", "").strip()
    if user_input == button_data.get("back_text", "⬅ Back"):
        return redirect(url_for('bereavement_chatbot'))

    button_info = button_data.get(user_input, {})
    reply = button_info.get("note") or button_info.get("question", "")
    options = button_info.get("options", [])
    
    if button_info.get("options"): # Add back button only if there are sub-options
        options.append(button_data.get("back_text", "⬅ Back"))
    else:
        options = button_data["main_buttons"]

    if "action" in button_info:
        role = "cna" if button_info["action"] == "Notify CNA" else "nurse"
        subject = f"{role.upper()} Request"
        notification_text = reply or button_data[f"{role}_notification"]
        reply = notify_and_log(role, subject, user_input, notification_text)
        options = button_data["main_buttons"]

    return render_template("chat.html", reply=reply, options=options, button_data=button_data)

@app.route("/reset-language")
def reset_language():
    """Allows changing the language by clearing it from the session."""
    session.pop("language", None)
    return redirect(url_for("language_selector"))

# --- Staff-Facing Routes ---
@app.route("/dashboard")
def dashboard():
    """The real-time dashboard for staff to see incoming requests."""
    return render_template("dashboard.html")

@app.route('/analytics')
def analytics():
    """The analytics dashboard to show trends and key metrics."""
    try:
        with engine.connect() as connection:
            # --- Query 1: Get counts for each request category ---
            top_requests_result = connection.execute(text(
                "SELECT category, COUNT(id) FROM requests GROUP BY category ORDER BY COUNT(id) DESC;"
            ))
            top_requests_data = top_requests_result.fetchall()
            
            top_requests_labels = [row[0] for row in top_requests_data]
            top_requests_values = [row[1] for row in top_requests_data]

            # --- Query 2: Get request counts by hour of the day ---
            requests_by_hour_result = connection.execute(text("""
                SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(id) 
                FROM requests 
                GROUP BY hour 
                ORDER BY hour;
            """))
            requests_by_hour_data = requests_by_hour_result.fetchall()

            # Process data to ensure all 24 hours are represented
            hourly_counts = defaultdict(int)
            for hour, count in requests_by_hour_data:
                hourly_counts[int(hour)] = count
            
            requests_by_hour_labels = [f"{h}:00" for h in range(24)]
            requests_by_hour_values = [hourly_counts[h] for h in range(24)]

    except Exception as e:
        print(f"ERROR fetching analytics data: {e}")
        # Provide empty data to prevent the page from crashing
        top_requests_labels, top_requests_values = [], []
        requests_by_hour_labels, requests_by_hour_values = [], []

    return render_template(
        'analytics.html',
        top_requests_labels=json.dumps(top_requests_labels),
        top_requests_values=json.dumps(top_requests_values),
        requests_by_hour_labels=json.dumps(requests_by_hour_labels),
        requests_by_hour_values=json.dumps(requests_by_hour_values)
    )

# --- SocketIO Event Handlers ---
@socketio.on('defer_request')
def handle_defer_request(data):
    """Handles the 'defer' event from the staff dashboard."""
    socketio.emit('request_deferred', data)

# --- App Startup ---
with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)

