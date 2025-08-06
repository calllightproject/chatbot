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

app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")
socketio = SocketIO(app, async_mode='eventlet')

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///local_call_light.db"
engine = create_engine(DATABASE_URL)

# --- Setup Database ---
def setup_database():
    with engine.connect() as conn:
        conn.execute(text("""
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
        conn.commit()

# --- Request Logging ---
def log_request_to_db(request_id, category, user_input, reply):
    room = session.get("room_number", "Unknown")
    is_first_baby = session.get("is_first_baby")
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO requests (request_id, timestamp, room, category, user_input, reply, is_first_baby)
            VALUES (:id, :ts, :room, :cat, :input, :reply, :baby);
        """), {
            "id": request_id,
            "ts": datetime.now(),
            "room": room,
            "cat": category,
            "input": user_input,
            "reply": reply,
            "baby": is_first_baby
        })
        conn.commit()

# --- Email Alert ---
def send_email_alert(subject, body):
    sender = os.getenv("EMAIL_USER")
    pwd = os.getenv("EMAIL_PASSWORD")
    to = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
    if not sender or not pwd:
        return
    msg = EmailMessage()
    msg["Subject"] = f"Room {session.get('room_number', 'N/A')} - {subject}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, pwd)
            smtp.send_message(msg)
    except:
        pass

# --- Process Request ---
def process_request(role, subject, user_input, reply):
    request_id = "req_" + str(datetime.now().timestamp()).replace('.', '')
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

# --- Routes ---
@app.route("/room/<room_id>")
def set_room(room_id):
    session.clear()
    session["room_number"] = room_id
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    active_requests_by_room = {}
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT request_id, room, user_input, category as role, timestamp
                FROM requests
                WHERE completion_timestamp IS NULL
                ORDER BY timestamp DESC;
            """))
            for row in result:
                room = row.room
                if room not in active_requests_by_room:
                    active_requests_by_room[room] = []
                active_requests_by_room[room].append({
                    'id': row.request_id,
                    'room': room,
                    'request': row.user_input,
                    'role': row.role,
                    'timestamp': row.timestamp.isoformat()
                })
    except Exception as e:
        print(f"Error fetching dashboard: {e}")
    return render_template("dashboard.html", active_requests_by_room=active_requests_by_room)

@socketio.on('acknowledge_request')
def handle_acknowledge(data):
    room = data['room']
    socketio.emit('status_update', {'message': data['message']}, to=room)

@socketio.on('defer_request')
def handle_defer_request(data):
    socketio.emit('request_deferred', data)

@socketio.on('complete_request')
def handle_complete_request(data):
    request_id = data.get('request_id')
    if request_id:
        with engine.connect() as connection:
            connection.execute(text("""
                UPDATE requests SET completion_timestamp = :now
                WHERE request_id = :req;
            """), {"now": datetime.now(), "req": request_id})
            connection.commit()

with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=False, use_reloader=False)
