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
from sqlalchemy.pool import NullPool

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")
socketio = SocketIO(app, async_mode='eventlet')

# --- KNOWLEDGE BASE ---
KNOWLEDGE_BASE = """
PASTE YOUR KNOWLEDGE BASE TEXT HERE
"""

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local_call_light.db")
engine = create_engine(DATABASE_URL, poolclass=NullPool)

# --- Database Setup ---
def setup_database():
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS requests (
                id SERIAL PRIMARY KEY,
                request_id VARCHAR(255) UNIQUE,
                timestamp TIMESTAMP,
                completion_timestamp TIMESTAMP,
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

# --- Helpers ---
def log_request_to_db(request_id, category, user_input, reply):
    room = session.get("room_number", "Unknown Room")
    is_first_baby = session.get("is_first_baby")
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO requests (request_id, timestamp, room, category, user_input, reply, is_first_baby)
                VALUES (:request_id, :timestamp, :room, :category, :user_input, :reply, :is_first_baby)
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
        print(f"[DB ERROR] {e}")

def send_email_alert(subject, body):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
    if not sender_email or not sender_password:
        print("[EMAIL WARNING] Missing credentials")
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
        print(f"[EMAIL ERROR] {e}")

def process_request(role, subject, user_input, reply):
    request_id = 'req_' + str(datetime.now().timestamp()).replace('.', '')
    socketio.start_background_task(send_email_alert, subject, user_input)
    socketio.start_background_task(log_request_to_db, request_id, role, user_input, reply)
    socketio.emit('new_request', {
        'id': request_id,
        'room': session.get('room_number', 'N/A'),
        'request': user_input,
        'role': role,
        'timestamp': datetime.now().isoformat()
    })
    return reply

def get_ai_response(question, context):
    keywords = {
        "nurse": ["pain", "bleeding", "dizzy", "nausea", "headache", "emergency"],
        "cna": ["water", "blanket", "pillow", "pad"]
    }
    q = question.lower()
    if any(k in q for k in keywords["nurse"]):
        return "NURSE_ACTION"
    if any(k in q for k in keywords["cna"]):
        return "CNA_ACTION"
    return "CANNOT_ANSWER"

# --- Routes ---
@app.route("/room/<room_id>")
def set_room(room_id):
    session.clear()
    session["room_number"] = room_id
    session["pathway"] = "standard"
    return redirect(url_for("language_selector"))

@app.route("/")
def language_selector():
    return render_template("language.html")

@app.route("/chat", methods=["GET", "POST"])
def chat():
    return render_template("chat.html")

@app.route("/dashboard")
def dashboard():
    active_requests = []
    try:
        with engine.begin() as connection:
            result = connection.execute(text("""
                SELECT request_id, room, user_input, category, timestamp
                FROM requests WHERE completion_timestamp IS NULL
                ORDER BY timestamp DESC;
            """))
            for row in result:
                active_requests.append({
                    "id": row.request_id,
                    "room": row.room or "N/A",
                    "request": row.user_input,
                    "role": row.category,
                    "timestamp": row.timestamp.isoformat()
                })
    except Exception as e:
        print(f"[DASHBOARD ERROR] {e}")
        return "Internal Server Error", 500
    return render_template("dashboard.html", active_requests=active_requests)

@socketio.on("acknowledge_request")
def ack(data):
    socketio.emit("status_update", {"message": data["message"]}, to=data["room"])

@socketio.on("defer_request")
def defer(data):
    socketio.emit("request_deferred", data)

@socketio.on("complete_request")
def complete(data):
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                UPDATE requests SET completion_timestamp = :now WHERE request_id = :rid
            """), {"now": datetime.now(), "rid": data["request_id"]})
        socketio.emit("request_completed", {"request_id": data["request_id"]})
    except Exception as e:
        print(f"[COMPLETE ERROR] {e}")

# --- Init ---
with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
