import os
import csv
from datetime import datetime
import smtplib
from email.message import EmailMessage
import importlib

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO

# --- App Configuration ---
# This version includes the template_folder fix
app = Flask(__name__, template_folder='templates')
app.secret_key = "a-very-long-and-random-secret-key-that-does-not-need-to-be-changed"
socketio = SocketIO(app)


# --- Helper Functions ---
def log_request(filename, user_input, category, reply):
    # This version includes the fix to write logs to the /tmp directory
    log_path = os.path.join('/tmp', filename)
    room = session.get("room_number", "Unknown Room")
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(["Timestamp", "Room", "User Input", "Category", "Reply"])
        writer.writerow([datetime.now(), room, user_input, category, reply])


def send_email_alert(to, subject, body):
    # This version correctly uses environment variables for secrets
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    if not sender_email or not sender_password:
        print("ERROR: Email credentials not set in Environment Variables.")
        return
    msg = EmailMessage()
    msg["Subject"] = f"Room {session.get('room_number', 'N/A')} - {subject}"
    msg["From"] = sender_email
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Email failed to send: {e}")


def notify_and_log(role, subject, user_input, reply_message):
    # --- THIS IS THE FIX: All alerts now go to your specified email ---
    recipient = "call.light.project@gmail.com"
    send_email_alert(recipient, subject, user_input)
    log_request(f"{role}_log.csv", user_input, role, reply_message)
    socketio.emit('new_request', {
        'room': session.get('room_number', 'N/A'),
        'request': user_input,
        'role': role
    })
    return reply_message


# --- Routes ---
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
            return redirect(url_for("bereavement_chatbot"))
        else:
            return redirect(url_for("chatbot"))
    return render_template("language.html")


@app.route("/reset-language")
def reset_language():
    session.pop("language", None)
    return redirect(url_for("language_selector"))


@app.route("/chat", methods=["GET", "POST"])
def chatbot():
    pathway = session.get("pathway", "standard")
    if pathway != "standard":
        return redirect(url_for("language_selector"))

    lang = session.get("language", "en")
    button_config = importlib.import_module(f"button_config_{lang}")
    chat_logic = importlib.import_module(f"chat_logic_{lang}")
    button_data = button_config.button_data
    classify_message = chat_logic.classify_message
    get_education_response = chat_logic.get_education_response

    if request.method == "GET":
        return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"])

    # --- Logic for POST requests (user submitting a form) ---
    if request.form.get("action") == "send_note":
        note_text = request.form.get("custom_note")
        reply = notify_and_log("nurse", "Custom Patient Note", note_text,
                               button_data["nurse_notification"]) if note_text else "Please type a message in the box."
        return render_template("chat.html", reply=reply, options=button_data["main_buttons"])

    user_input = request.form.get("user_input", "").strip()
    if user_input == "⬅ Back":
        return redirect(url_for('chatbot'))

    reply = ""
    options = button_data["main_buttons"]

    if user_input in button_data:
        button_info = button_data[user_input]
        if "question" in button_info:
            reply = button_info["question"]
            options = button_info.get("options", []) + ["⬅ Back"]
        elif "note" in button_info:
            reply = button_info["note"]
            if "options" in button_info:
                options = button_info.get("options", []) + ["⬅ Back"]

        if "action" in button_info:
            action = button_info["action"]
            notification_text = reply or (
                button_data["nurse_notification"] if action == "Notify Nurse" else button_data["cna_notification"])
            if action == "Notify CNA":
                reply = notify_and_log("cna", "CNA Request", user_input, notification_text)
            elif action == "Notify Nurse":
                reply = notify_and_log("nurse", "Nurse Request", user_input, notification_text)
            options = button_data["main_buttons"]
    else:
        category = classify_message(user_input)
        if category == "education":
            reply = get_education_response(user_input)
        else:
            role = "nurse" if category == "urgent" else category if category in ["nurse", "cna"] else "nurse"
            subject = f"{category.upper()} Request" if category != "unknown" else "Unknown Request"
            reply = notify_and_log(role, subject, user_input, button_data[f"{role}_notification"])
        options = button_data["main_buttons"]

    return render_template("chat.html", reply=reply, options=options)


@app.route("/bereavement-chat", methods=["GET", "POST"])
def bereavement_chatbot():
    pathway = session.get("pathway", "standard")
    if pathway != "bereavement":
        return redirect(url_for("language_selector"))

    lang = session.get("language", "en")
    button_config = importlib.import_module(f"button_config_bereavement_{lang}")
    button_data = button_config.button_data

    if request.method == "GET":
        return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"])

    user_input = request.form.get("user_input", "").strip()
    if user_input == "⬅ Back":
        return redirect(url_for('bereavement_chatbot'))

    button_info = button_data.get(user_input, {})
    reply = button_info.get("note") or button_info.get("question", "")
    options = button_info.get("options", button_data["main_buttons"])
    if "question" in button_info or "options" in button_info:
        options += ["⬅ Back"]

    if "action" in button_info:
        action = button_info["action"]
        notification_text = reply or (
            button_data["nurse_notification"] if action == "Notify Nurse" else button_data["cna_notification"])
        if action == "Notify CNA":
            reply = notify_and_log("cna", "CNA Request", user_input, notification_text)
        elif action == "Notify Nurse":
            reply = notify_and_log("nurse", "Nurse Request", user_input, notification_text)
        options = button_data["main_buttons"]

    return render_template("chat.html", reply=reply, options=options)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# --- SocketIO Event Handlers ---
@socketio.on('defer_request')
def handle_defer_request(data):
    socketio.emit('request_deferred', data)


# --- Run Application ---
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', debug=True, use_reloader=False)
