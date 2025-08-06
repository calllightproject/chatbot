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
socketio = SocketIO(app, async_mode='eventlet')

# --- KNOWLEDGE BASE ---
KNOWLEDGE_BASE = """
PASTE YOUR KNOWLEDGE BASE TEXT HERE
"""

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

# --- Core Helper Functions ---
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
    sender_email = os.getenv("EMAIL_USE
