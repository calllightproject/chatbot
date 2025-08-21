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
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*", manage_session=False, ping_timeout=20, ping_interval=10)

# --- Master Data Lists ---
INITIAL_STAFF = {
    'Jackie': 'nurse', 'Carol': 'nurse', 'John': 'nurse',
    'Maria': 'nurse', 'David': 'nurse', 'Susan': 'nurse',
    'Peter': 'cna', 'Linda': 'cna' 
}
# Define the room zones for CNAs
CNA_FRONT_ROOMS = [str(r) for r in range(231, 245)] + ['260']
CNA_BACK_ROOMS = [str(r) for r in range(245, 260)]
ALL_ROOMS = sorted(CNA_FRONT_ROOMS + CNA_BACK_ROOMS)


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
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS requests (
                        id SERIAL PRIMARY KEY, request_id VARCHAR(255) UNIQUE, timestamp TIMESTAMP WITH TIME ZONE,
                        completion_timestamp TIMESTAMP WITH TIME ZONE, deferral_timestamp TIMESTAMP WITH TIME ZONE,
                        room VARCHAR(255), user_input TEXT, category VARCHAR(255), reply TEXT, is_first_baby BOOLEAN
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS assignments (
                        id SERIAL PRIMARY KEY, assignment_date DATE NOT NULL, room_number VARCHAR(255) NOT NULL,
                        staff_name VARCHAR(255) NOT NULL, staff_role VARCHAR(50), 
                        UNIQUE(assignment_date, room_number)
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY, timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                        event_type VARCHAR(255) NOT NULL, details TEXT
                    );
                """))
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS staff (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        role VARCHAR(50) NOT NULL
                    );
                """))
                print("CREATE TABLE statements complete.")

                count = connection.execute(text("SELECT COUNT(id) FROM staff;")).scalar()
                if count == 0:
                    print("Staff table is empty. Populating with initial staff...")
                    for name, role in INITIAL_STAFF.items():
                        connection.execute(text("""
                            INSERT INTO staff (name, role) VALUES (:name, :role)
                            ON CONFLICT (name) DO NOTHING;
                        """), {"name": name, "role": role})
                    print("Initial staff population complete.")

        with engine.connect() as connection:
            with connection.begin():
                try:
                    connection.execute(text("ALTER TABLE requests ADD COLUMN deferral_timestamp TIMESTAMP WITH TIME ZONE;"))
                except ProgrammingError: pass
                try:
                    connection.execute(text("ALTER TABLE assignments RENAME COLUMN nurse_name TO staff_name;"))
                except ProgrammingError: pass
                try:
                    connection.execute(text("ALTER TABLE assignments ADD COLUMN staff_role VARCHAR(50);"))
                except ProgrammingError: pass
        
        print("Database setup complete. Tables are ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

setup_database()

# --- Smart Routing Logic ---
def route_note_intelligently(note_text):
    NURSE_KEYWORDS = ['pain', 'medication', 'bleeding', 'nausea', 'dizzy', 'sick', 'iv', 'pump', 'staples', 'incision']
    note_lower = note_text.lower()
    for keyword in NURSE_KEYWORDS:
        if keyword in note_lower:
            return 'nurse'
    return 'cna'

# --- Core Helper Functions (Unchanged) ---
# ... (log_to_audit_trail, log_request_to_db, send_email_alert, process_request) ...

# --- App Routes ---
# ... (room, bereavement, language_selector, demographics, chat, reset_language, dashboard, analytics, manager_dashboard routes are unchanged) ...

# MODIFIED: This route now handles the new, simpler assignment logic.
@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    today = date.today()
    
    if request.method == 'POST':
        try:
            with engine.connect() as connection:
                with connection.begin():
                    # Clear today's old assignments first
                    connection.execute(text("DELETE FROM assignments WHERE assignment_date = :date;"), {"date": today})

                    # Process Nurse assignments
                    for key, value in request.form.items():
                        if key.startswith('nurse_rooms_'):
                            nurse_name = key.replace('nurse_rooms_', '')
                            assigned_rooms = request.form.getlist(key)
                            for room_number in assigned_rooms:
                                connection.execute(text("""
                                    INSERT INTO assignments (assignment_date, room_number, staff_name, staff_role)
                                    VALUES (:date, :room, :name, 'nurse');
                                """), {"date": today, "room": room_number, "name": nurse_name})
                    
                    # Process CNA assignments
                    cna_front = request.form.get('cna_front')
                    if cna_front and cna_front != 'unassigned':
                        for room_number in CNA_FRONT_ROOMS:
                            connection.execute(text("""
                                INSERT INTO assignments (assignment_date, room_number, staff_name, staff_role)
                                VALUES (:date, :room, :name, 'cna');
                            """), {"date": today, "room": room_number, "name": cna_front})

                    cna_back = request.form.get('cna_back')
                    if cna_back and cna_back != 'unassigned':
                        for room_number in CNA_BACK_ROOMS:
                            connection.execute(text("""
                                INSERT INTO assignments (assignment_date, room_number, staff_name, staff_role)
                                VALUES (:date, :room, :name, 'cna');
                            """), {"date": today, "room": room_number, "name": cna_back})

            print("Assignments saved successfully.")
        except Exception as e:
            print(f"ERROR saving assignments: {e}")
        return redirect(url_for('assignments'))

    # For a GET request, fetch data for the page
    all_nurses, all_cnas, current_assignments = [], [], {}
    try:
        with engine.connect() as connection:
            nurses_result = connection.execute(text("SELECT name FROM staff WHERE role = 'nurse' ORDER BY name;"))
            all_nurses = [row[0] for row in nurses_result]
            
            cnas_result = connection.execute(text("SELECT name FROM staff WHERE role = 'cna' ORDER BY name;"))
            all_cnas = [row[0] for row in cnas_result]

            assignments_result = connection.execute(text("SELECT room_number, staff_name, staff_role FROM assignments WHERE assignment_date = :date;"), {"date": today})
            for row in assignments_result:
                current_assignments[row.room_number] = {"name": row.staff_name, "role": row.staff_role}
    except Exception as e:
        print(f"ERROR fetching assignment data: {e}")
    
    return render_template('assignments.html', 
                           all_nurses=all_nurses, 
                           all_cnas=all_cnas,
                           all_rooms=ALL_ROOMS,
                           cna_front_rooms=CNA_FRONT_ROOMS,
                           cna_back_rooms=CNA_BACK_ROOMS,
                           current_assignments=current_assignments)

# --- SocketIO Event Handlers (Unchanged) ---
# ... (join, acknowledge_request, defer_request, complete_request) ...
