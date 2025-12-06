import eventlet
eventlet.monkey_patch()

import os
import json
import smtplib
import importlib
import re
import difflib

from datetime import datetime, date, time, timezone
from collections import defaultdict
from email.message import EmailMessage

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, abort
from flask_socketio import SocketIO, join_room
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from werkzeug.security import generate_password_hash, check_password_hash


# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")
socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    manage_session=False,
    ping_timeout=60,   # was 20
    ping_interval=25   # was 10
)

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


# --- Room Configuration ---
ALL_ROOMS = [str(room) for room in range(231, 260)]
VALID_ROOMS = set(ALL_ROOMS)

# (Removed conflicting /room/<room_number> route here)

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

                # Core tables
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS requests (
                        id SERIAL PRIMARY KEY,
                        request_id VARCHAR(255) UNIQUE,
                        timestamp TIMESTAMPTZ,
                        completion_timestamp TIMESTAMPTZ,
                        deferral_timestamp TIMESTAMPTZ,
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
                        shift VARCHAR(10) NOT NULL,
                        room_number VARCHAR(255) NOT NULL,
                        staff_name VARCHAR(255) NOT NULL,
                        UNIQUE (assignment_date, shift, room_number)
                    );
                """))

                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL,
                        event_type VARCHAR(255) NOT NULL,
                        details TEXT
                    );
                """))

                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS staff (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        role VARCHAR(50) NOT NULL,
                        preferred_shift VARCHAR(10),
                        languages TEXT,
                        pin_hash TEXT,
                        pin_set_at TIMESTAMPTZ
                    );
                """))

                # CNA coverage (front/back per shift)
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS cna_coverage (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        shift VARCHAR(10) NOT NULL,
                        zone VARCHAR(20) NOT NULL,   -- 'front' / 'back'
                        cna_name VARCHAR(255),
                        UNIQUE (assignment_date, shift, zone)
                    );
                """))

                # Room state: reset marker + future tags (JSONB)
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS room_state (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        shift VARCHAR(10) NOT NULL,
                        room_number VARCHAR(20) NOT NULL,
                        reset_at TIMESTAMPTZ,
                        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                        UNIQUE (assignment_date, shift, room_number)
                    );
                """))

                print("CREATE TABLE statements complete.")

                # ---------------- Idempotent hardening ----------------

                # Ensure 'shift' column exists on older DBs (harmless if already there)
                try:
                    connection.execute(text("""
                        ALTER TABLE assignments
                        ADD COLUMN IF NOT EXISTS shift VARCHAR(10) NOT NULL DEFAULT 'day';
                    """))
                    connection.execute(text("""
                        ALTER TABLE assignments
                        ALTER COLUMN shift DROP DEFAULT;
                    """))
                except Exception:
                    pass

                # Ensure correct UNIQUE(date, shift, room) on assignments
                try:
                    connection.execute(text("""
                        DO $$
                        BEGIN
                          IF NOT EXISTS (
                            SELECT 1
                            FROM   pg_constraint
                            WHERE  conname = 'assignments_uniq_date_shift_room'
                          ) THEN
                            ALTER TABLE assignments
                            ADD CONSTRAINT assignments_uniq_date_shift_room
                            UNIQUE (assignment_date, shift, room_number);
                          END IF;
                        END$$;
                    """))
                except Exception:
                    pass

                # Backfill safe defaults
                try:
                    connection.execute(text("""
                        UPDATE room_state
                        SET tags = COALESCE(tags, '[]'::jsonb);
                    """))
                except Exception:
                    pass

                try:
                    connection.execute(text("""
                        UPDATE staff
                        SET languages = COALESCE(languages, '["en"]');
                    """))
                except Exception:
                    pass

                # Ensure PIN columns exist on older DBs
                try:
                    connection.execute(text("""
                        ALTER TABLE staff
                        ADD COLUMN IF NOT EXISTS pin_hash TEXT;
                    """))
                    connection.execute(text("""
                        ALTER TABLE staff
                        ADD COLUMN IF NOT EXISTS pin_set_at TIMESTAMPTZ;
                    """))
                except Exception:
                    pass

        # Legacy safety: make sure deferral_timestamp exists
        try:
            with engine.connect() as connection:
                with connection.begin():
                    connection.execute(text("""
                        ALTER TABLE requests
                        ADD COLUMN IF NOT EXISTS deferral_timestamp TIMESTAMPTZ;
                    """))
        except Exception:
            pass

        print("Database setup complete. Tables are ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

setup_database()

# --- Localized label -> English maps for structured buttons ---
ES_TO_EN = {
    "Tengo una emergencia": "I'm having an emergency",
    "Necesito suministros": "I need supplies",
    "Necesito medicamentos": "I need medication",
    "Mi bomba de IV está sonando": "My IV pump is beeping",
    "Tengo preguntas": "I have questions",
    "Quiero saber sobre el alta": "I want to know about going home",
    "Baño / Ducha": "Bathroom/Shower",
    "Necesito ayuda para amamantar": "I need help breastfeeding",
    "Azúcar en la sangre": "Blood sugar",
    "Hielo / Agua": "Ice Chips/Water",

    "Mamá (azúcar en la sangre)": "Mom (blood sugar)",
    "Bebé (azúcar en la sangre)": "Baby (blood sugar)",

    "Necesito agua con hielo": "I need ice water",
    "Necesito hielo picado": "I need ice chips",
    "Necesito agua, sin hielo": "I need water, no ice",
    "Necesito agua caliente": "I need hot water",

    "Necesito ayuda para ir al baño": "I need help to the bathroom",
    "Necesito cubrir mi vía IV para bañarme": "I need my IV covered to shower",
    "¿Puedo tomar una ducha?": "Can I take a shower?",

    "Artículos para bebé": "Baby items",
    "Artículos para mamá": "Mom items",
    "Pañales": "Diapers",
    "Fórmula": "Formula",
    "Manta para envolver": "Swaddle",
    "Toallitas húmedas": "Wipes",
    "Toallas sanitarias": "Pads",
    "Ropa interior de malla": "Mesh underwear",
    "Compresa de hielo": "Ice pack",
    "Almohadas": "Pillows",

    "Toallas azules": "Blue pads",
    "Toallas blancas": "White pads",

    "Compresa de hielo para el perineo": "Ice Pack for Bottom",
    "Compresa de hielo para la incisión de la cesárea": "Ice Pack for C-section incision",
    "Compresa de hielo para los senos": "Ice Pack for Breasts",

    "Similac Total Comfort (etiqueta morada)": "Similac Total Comfort (purple label)",
    "Similac 360 (etiqueta azul)": "Similac 360 (blue label)",
    "Similac Neosure (etiqueta amarilla)": "Similac Neosure (yellow label)",
    "Enfamil Newborn (etiqueta amarilla)": "Enfamil Newborn (yellow label)",
    "Enfamil Gentlease (etiqueta morada)": "Enfamil Gentlease (purple label)",

    "Dolor": "Pain",
    "Náuseas/Vómitos": "Nausea/Vomiting",
    "Picazón": "Itchy",
    "Dolor por gases": "Gas pain",
    "Estreñimiento": "Constipation",
}

ZH_TO_EN = {
    "我有紧急情况": "I'm having an emergency",
    "我需要用品": "I need supplies",
    "我需要药物": "I need medication",
    "我的静脉输液泵在响": "My IV pump is beeping",
    "我有问题": "I have questions",
    "我想了解出院信息": "I want to know about going home",
    "浴室/淋浴": "Bathroom/Shower",
    "我需要母乳喂养方面的帮助": "I need help breastfeeding",
    "血糖": "Blood sugar",
    "冰块/水": "Ice Chips/Water",

    "妈妈（血糖）": "Mom (blood sugar)",
    "宝宝（血糖）": "Baby (blood sugar)",

    "我需要冰水": "I need ice water",
    "我需要冰块": "I need ice chips",
    "我需要不加冰的水": "I need water, no ice",
    "我需要热水": "I need hot water",

    "我需要帮助去卫生间": "I need help to the bathroom",
    "我需要包裹我的静脉输液管以便洗澡": "I need my IV covered to shower",
    "我可以洗澡吗？": "Can I take a shower?",

    "宝宝用品": "Baby items",
    "妈妈用品": "Mom items",
    "尿布": "Diapers",
    "配方奶": "Formula",
    "襁褓巾": "Swaddle",
    "湿巾": "Wipes",
    "卫生巾": "Pads",
    "网眼内裤": "Mesh underwear",
    "冰袋": "Ice pack",
    "枕头": "Pillows",

    "蓝色卫生巾": "Blue pads",
    "白色卫生巾": "White pads",

    "用于会阴部的冰袋": "Ice Pack for Bottom",
    "用于剖腹产切口的冰袋": "Ice Pack for C-section incision",
    "用于乳房的冰袋": "Ice Pack for Breasts",

    "Similac Total Comfort (紫色标签)": "Similac Total Comfort (purple label)",
    "Similac 360 (蓝色标签)": "Similac 360 (blue label)",
    "Similac Neosure (黄色标签)": "Similac Neosure (yellow label)",
    "Enfamil Newborn (黄色标签)": "Enfamil Newborn (yellow label)",
    "Enfamil Gentlease (紫色标签)": "Enfamil Gentlease (purple label)",

    "疼痛": "Pain",
    "恶心/呕吐": "Nausea/Vomiting",
    "瘙痒": "Itchy",
    "胀气痛": "Gas pain",
    "便秘": "Constipation",
}

def to_english_label(text: str, lang: str) -> str:
    """Return an English label for structured buttons. For unknown/custom notes, tag language."""
    if not text:
        return text
    if lang == "es":
        return ES_TO_EN.get(text, f"[ES] {text}")
    if lang == "zh":
        return ZH_TO_EN.get(text, f"[ZH] {text}")
    return text

def migrate_schema():
    try:
        with engine.connect() as connection:
            with connection.begin():
                # staff.preferred_shift
                connection.execute(text("""
                    ALTER TABLE staff
                    ADD COLUMN IF NOT EXISTS preferred_shift VARCHAR(10);
                """))

                # assignments.shift
                connection.execute(text("""
                    ALTER TABLE assignments
                    ADD COLUMN IF NOT EXISTS shift VARCHAR(10);
                """))

                # unique index for (date, shift, room)
                connection.execute(text("""
                    CREATE UNIQUE INDEX IF NOT EXISTS assignments_unique_triplet
                    ON assignments (assignment_date, shift, room_number);
                """))

                # cna_coverage table
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS cna_coverage (
                        id SERIAL PRIMARY KEY,
                        assignment_date DATE NOT NULL,
                        shift VARCHAR(10),
                        zone VARCHAR(20) NOT NULL,
                        cna_name VARCHAR(255),
                        UNIQUE (assignment_date, shift, zone)
                    );
                """))
        print("Schema migration OK.")
    except Exception as e:
        print(f"Schema migration error: {e}")

def send_email_alert(subject, body, room_number):
    """Safe/no-op email alert. Will quietly skip if creds aren’t set."""
    try:
        sender_email = os.getenv("EMAIL_USER")
        sender_password = os.getenv("EMAIL_PASSWORD")
        recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
        if not sender_email or not sender_password:
            return  # no creds → skip
        msg = EmailMessage()
        msg["Subject"] = f"Room {room_number} - {subject}"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
    except Exception as e:
        print(f"EMAIL disabled or failed: {e}")

import re
from collections import Counter

# =========================================================
# Helpers
# =========================================================

def _normalize_text(text: str) -> str:
    """Lowercase and trim; safe handling of None."""
    return (text or "").strip().lower()


# =========================================================
# HEART / BREATH / COLOR / PPH EMERGENT
# =========================================================

def _has_heart_breath_color_emergent(text: str) -> bool:
    """
    Very liberal emergent screener for:
      - chest/heart
      - breathing/airway
      - color change (cyanosis)
      - heavy postpartum bleeding / hemorrhage (PPH)
    ENGLISH ONLY.

    If this returns True, we will:
      - route to NURSE
      - classify as EMERGENT
    """
    if not text:
        return False

    # Normalize case + curly quotes
    t = text.lower().strip()
    t = t.replace("’", "'").replace("“", '"').replace("”", '"')

    # -------- 1. INSTANT STRING TRIGGERS (on their own are emergent) --------
    instant_triggers = [
        # can't breathe / no air
        "can't breathe", "cant breathe", "cannot breathe",
        "can't get air", "cant get air",
        "can't catch my breath", "cant catch my breath",
        "short of breath", "shortness of breath",
        "out of breath",
        "no air", "not getting air",
        "can't pull in a breath", "cant pull in a breath",
        "can't get a breath", "cant get a breath",
        "gasping for air", "gasp for air", "gasping",
        "suffocating", "suffocate", "feel like i am suffocating",
        "throat is closing",

        # common phrases
        "trouble breathing", "having trouble breathing",
        "hard time breathing", "difficulty breathing",

        # very explicit baby emergencies
        "baby suddenly stopped breathing",
        "my baby suddenly stopped breathing",
        "baby stopped breathing",
        "baby not breathing",
        "my baby not breathing",
        "baby isn't breathing", "baby isnt breathing",
        "my baby isn't breathing", "my baby isnt breathing",
        "baby can't breathe", "baby cant breathe",
        "baby's chest isn't rising", "baby chest isn't rising",
        "baby chest isnt rising",
    ]
    for kw in instant_triggers:
        if kw in t:
            return True

    # -------- 2. BREATHING / AIRWAY PATTERNS --------
    breath_tokens = [
        "breath", "breathe", "breathing",
        "air", "lungs", "inhale", "exhale",
        "short of breath", "shortness of breath",
        "can't catch my breath", "cant catch my breath",
    ]
    breath_severity = [
        "hard", "harder",
        "struggling", "struggle",
        "trouble", "difficulty",
        # removed "getting worse" / "worse" so we don't misread
        # "my cramps are getting worse but I am breathing fine"
        # as a breathing emergency
        "stopping", "stopped", "keeps stopping", "keeps pausing", "pausing",
        "shallow", "irregular",
        "scary", "frightening", "terrified",
        "about to faint", "going to faint", "going to pass out",
        "locking up", "locked up", "blocked", "blocking",
        "can't", "cant", "cannot",
        "no air", "not getting air",
        # softer language that still means “off”
        "weird", "off", "funny",
    ]

    if any(tok in t for tok in breath_tokens) and any(s in t for s in breath_severity):
        return True

    # e.g. "I suddenly can't feel air moving in or out of my lungs"
    if "air moving" in t and "lungs" in t:
        return True
    if "can't feel air" in t or "cant feel air" in t:
        return True

    # -------- 3. HEART PATTERNS --------
    if "heart" in t:
        heart_severity = [
            "racing", "pounding", "beating so fast", "beating fast",
            "beating out of my chest",
            "skipping", "skips", "skipped",
            "stopping", "stopped",
            "flutter", "fluttering",
            "erratic", "out of control",
            "weak", "not normal", "not right",
            "wrong", "off", "weird",
            "scares", "scared", "dangerous",
            "feels like it's stopping for a second and restarting",
            "feels like its stopping for a second and restarting",
        ]
        if any(s in t for s in heart_severity):
            return True

    # -------- 4. CHEST PAIN / PRESSURE PATTERNS --------
    if "chest" in t:
        chest_severity = [
            "pain", "hurts",
            "tight", "tightness",
            "pressure", "crushing", "crushed",
            "heavy", "weight",
            "locking up", "locked up",
            "squeezed", "squeezing",
            "center of my chest", "center of the chest",
            "across my whole chest",
        ]
        if any(s in t for s in chest_severity):
            return True

        # combo patterns with air
        if ("can't get air" in t or "cant get air" in t or
            "can't pull in a breath" in t or "cant pull in a breath" in t or
            "can't catch my breath" in t or "cant catch my breath" in t):
            return True

    # -------- 5. BABY + BREATHING (generic) --------
    if any(w in t for w in ["baby", "newborn", "infant"]):
        if any(p in t for p in [
            "not breathing", "isn't breathing", "isnt breathing",
            "stopped breathing", "chest isn't rising", "chest isnt rising",
            "breathing seems off", "breathing seems weird",
            "breathing looks weird", "breathing looks off",
        ]):
            return True

    # -------- 6. COLOR CHANGE (cyanosis) --------
    color_words = ["blue", "bluish", "purple", "grey", "gray"]
    body_part_words = [
        "skin", "face", "lips", "mouth",
        "hands", "hand", "feet", "foot",
        "fingers", "toes", "tongue", "nose",
        "baby", "newborn", "infant",
    ]

    # Color on a body part (avoid obvious supply contexts like pads/blankets)
    if any(c in t for c in color_words) and any(w in t for w in body_part_words):
        if not any(s in t for s in ["pad", "pads", "blanket", "sheets", "sheet", "pillow", "gown"]):
            return True

    # Explicit "my baby is blue" style phrases (extra hard-stop)
    if ("baby is blue" in t or "my baby is blue" in t or
        "baby looks blue" in t or "my baby looks blue"):
        return True

    if ("turned blue" in t or "turning blue" in t or
        "turned purple" in t or "turning purple" in t or
        "turned grey" in t or "turning grey" in t or
        "turned gray" in t or "turning gray" in t or
        "turned bluish" in t or "turning bluish" in t):
        return True

    # -------- 7. POSTPARTUM HEMORRHAGE (PPH) / HEAVY BLEEDING --------
    bleed_tokens = ["bleeding", "blood", "clot", "clots"]
    if any(b in t for b in bleed_tokens):

        # generic heavy-pad patterns (pad, sheet, floor, minutes)
        if "pad" in t and any(w in t for w in ["soak", "soaked", "soaking", "filling", "filled"]):
            return True
        if "pad" in t and "minutes" in t:
            return True
        if "bright red" in t and ("pad" in t or "sheet" in t or "floor" in t):
            return True
        if ("onto the floor" in t or "on the floor" in t) and any(w in t for w in ["blood", "bleeding"]):
            return True

        # strong severity phrases
        severe_bleed_phrases = [
            "running down my legs", "running down my leg",
            "down my legs", "down my leg",
            "gushing", "gushes", "pouring", "pours",
            "like a faucet", "blood everywhere",
            "soaking through pads", "soaking pads", "soaking my pad",
            "soaked through pad", "soaked through the pad",
            "pad was totally soaked", "pad is totally soaked",
            "totally soaked within an hour", "soaked within an hour",
            "bleeding a lot more than before",
            "bleeding a lot", "bleeding heavily", "bleeding is heavy",
            "won't stop", "wont stop", "not stopping",
            "keeps happening", "keeps getting worse", "getting worse",
        ]
        if any(p in t for p in severe_bleed_phrases):
            return True

        # bleeding + symptoms of hypovolemia
        hypovolemia_words = [
            "dizzy", "dizziness",
            "lightheaded", "light headed",
            "faint", "fainting", "about to faint",
            "going to faint", "going to pass out",
            "weak", "very weak",
            "shaky", "shake", "shaking",
            "cold", "sweaty", "clammy",
            "feel like i'm going to pass out", "feel like im going to pass out",
        ]
        if any(sym in t for sym in hypovolemia_words):
            return True

    # large clots (ALWAYS emergent)
    clot_phrases = [
        "big clots", "big clot",
        "large clots", "large clot",
        "clot the size of a golf ball",
        "clot the size of a softball",
        "clot the size of a baseball",
        "clot the size of my fist",
        "golf ball sized clot",
        "bigger than a quarter",
    ]
    if any(p in t for p in clot_phrases):
        return True

    return False


# =========================================================
# NEURO + HTN EMERGENT HELPERS
# =========================================================

EMERGENT_NEURO_PHRASES = [
    # --- Seizure activity / whole-body shaking ---
    "seizure", "seizing",
    "postictal", "convulsion", "convulsing",
    "my body is jerking", "body keeps jerking",
    "twitching uncontrollably", "twitching and jerking",
    "whole body suddenly started shaking",
    "whole body started shaking",
    "whole body feels shaky and sick",
    "my whole body feels shaky and sick",

    # --- Unresponsive / consciousness changes ---
    "unconscious", "not waking up",
    "can't wake", "cant wake",
    "won't wake", "wont wake",
    "blacking out", "blacked out",
    "fading out", "fading away",
    "can't stay conscious", "cant stay conscious",
    "in and out of consciousness",

    # --- Loss of awareness / confusion ---
    "suddenly confused",
    "extremely confused",
    "disoriented", "confused and disoriented",
    "can't think straight", "cant think straight",
    "can't understand", "cant understand",
    "can't make sense of", "cant make sense of",
    "brain is shutting down",

    # --- Speech disturbances ---
    "speech is slurred", "words are slurring",
    "slurred speech",
    "can't speak", "cant speak",
    "can't get any words out", "cant get any words out",
    "words sound scrambled",
    "can't form words", "cant form words",

    # --- Focal neurologic deficits ---
    "left side feels weak", "right side feels weak",
    "left side is weak", "right side is weak",
    "suddenly weak on one side",
    "face drooping", "drooping face",
    "crooked smile",
    "can't move my face", "cant move my face",
    "face feels numb", "mouth feels numb",
    "can't move my mouth", "cant move my mouth",
    "can't move my arm", "cant move my arm",
    "can't move my leg", "cant move my leg",
    "right arm dropped", "arm dropped suddenly",
    "legs collapsed", "legs gave out",
    "whole body went weak",
    "arms won't lift", "arms wont lift",

    # --- Severe headaches / neuro pain ---
    "worst headache of my life",
    "thunderclap headache",
    "head feels like it's exploding",
    "head feels like its exploding",
    "sudden exploding pain in my head",
    "intense pressure in my head",

    # --- Vision changes ---
    "vision fading", "vision going dark",
    "vision is dark", "tunnel vision",
    "spots in vision",
    "flashing lights", "seeing little flashing lights",
    "eyes rolling back",

    # --- Motor control problems ---
    "can't control my hands", "cant control my hands",
    "hands curling", "hands locked up",
    "body locked up", "muscles locking up",
    "can't move anything", "cant move anything",

    # --- Baby neuro red flags ---
    "my baby feels stiff",
    "my baby feels floppy",
    "my baby feels limp",
    "my baby is floppy",
    "my baby is limp",

    "my baby won't respond", "my baby wont respond",
    "baby not responding",

    "baby not waking", "baby wont wake",
    "baby is floppy", "baby feels floppy",
    "baby is limp", "baby feels limp",

    # NEW: baby not waking up (with and without apostrophe)
    "my baby isn't waking up", "my baby isnt waking up",
    "baby isn't waking up", "baby isnt waking up",

    # NEW: baby not reacting / won’t react
    "my baby won't react", "my baby wont react",
    "baby won't react", "baby wont react",
    "won't react", "wont react",
    "not reacting", "no reaction",

    "baby staring off", "baby staring through me",
    "baby keeps staring off",
    "eyes seem to drift upward", "eyes drift upward",
]


def _has_neuro_emergent(text: str) -> bool:
    """
    STRICT neurologic emergent screener (postpartum).

    If this returns True, classify as EMERGENT and route to NURSE.
    """
    if not text:
        return False

    t = text.lower().strip()
    t = t.replace("’", "'").replace("“", '"').replace("”", '"')

    # --- Equipment beeping / alarms should NOT trigger neuro emergent ---
    # e.g. "iv pump is beeping and won't stop", "bp cuff keeps erroring"
    if any(w in t for w in ["iv pump", "pump", "machine", "monitor", "cuff"]):
        if any(p in t for p in [
            "beeping", "alarm", "won't stop", "wont stop",
            "keeps beeping", "keeps going off", "occlusion"
        ]):
            return False

    # 1) Direct phrase hits from the master list
    for phrase in EMERGENT_NEURO_PHRASES:
        if phrase in t:
            return True

    # 2) Sudden problems with understanding or speaking
    if "sudden" in t or "suddenly" in t:
        if any(p in t for p in [
            "can't understand", "cant understand",
            "can't get any words out", "cant get any words out",
            "can't speak", "cant speak",
            "can't talk", "cant talk",
            "can't move my mouth", "cant move my mouth",
        ]):
            return True

        # sudden focal weakness / control loss
        if any(p in t for p in [
            "right arm", "left arm", "right hand", "left hand",
            "right leg", "left leg",
            "arm dropped", "dropped my arm",
            "leg gave out", "legs gave out",
        ]) and any(p in t for p in [
            "can't move", "cant move",
            "can't control", "cant control",
            "went weak", "feels weak",
        ]):
            return True

    # 3) Can't respond / can't move mouth when awake
    if any(p in t for p in ["can't respond", "cant respond"]):
        if any(p in t for p in [
            "move my mouth", "move my lips",
            "talk", "speak", "get words out",
        ]):
            return True

    # 4) Whole-body shaking / jerking
    if ("whole body" in t or "my whole body" in t) and any(
        w in t for w in ["shaky", "shaking", "jerking", "twitching"]
    ):
        return True

    # 5) Hands shaking violently and not stopping
    if "hands" in t and any(w in t for w in ["shaking", "jerking", "twitching"]):
        if any(p in t for p in [
            "can't make them stop", "cant make them stop",
            "can't control them", "cant control them",
            "won't stop", "wont stop",
        ]):
            return True

    # 6) Shaky + sick + sense something terrible is about to happen
    if any(w in t for w in ["shaky", "shaking"]) and "sick" in t:
        if any(p in t for p in [
            "something terrible is about to happen",
            "sense that something terrible is about to happen",
            "i feel this sense that something terrible is about to happen",
        ]):
            return True

    # 7) Focal weakness on one side
    if ("left side" in t or "right side" in t) and (
        "weak" in t or "weakness" in t or "heavy" in t
    ):
        if ("barely move" in t or "can barely move" in t or
            "can't move" in t or "cant move" in t):
            return True

    # 8) Crooked smile / facial asymmetry
    if "smile looks crooked" in t or ("crooked" in t and "smile" in t):
        return True
    if ("can't move" in t or "cant move" in t) and (
        "one side of my face" in t or "one side of my mouth" in t
    ):
        return True

    # 9) Can't stop shaking + body not responding
    if ("can't stop shaking" in t or "cant stop shaking" in t) and (
        "body won't respond" in t or "body wont respond" in t or
        "won't respond when i try to move" in t or "wont respond when i try to move" in t
    ):
        return True

    # 10) Baby suddenly stiff + eyes not focusing
    if "baby" in t and "stiff" in t and (
        "eyes won't focus" in t or "eyes wont focus" in t or
        "eyes not focusing" in t or "won't focus" in t or "wont focus" in t
    ):
        return True

    # 11) Baby floppy / unresponsive (ALWAYS emergent)
    if "baby" in t:
        floppy_patterns = [
            "feels floppy", "feels super floppy", "feels too floppy",
            "feels loose", "too loose",
            "arms feel floppy", "legs feel floppy",
            "arms feel loose", "legs feel loose",
            "body feels floppy", "body feels loose",
            "is floppy", "is super floppy",
            "arms just hang there", "legs just hang there",
            "just hang there loose", "hang there loose",
            "just hanging there loose",
        ]
        if any(p in t for p in floppy_patterns):
            return True

        unresponsive_patterns = [
            "not waking up", "not waking",
            "won't wake up", "wont wake up",
            "won't wake", "wont wake",
            "not responding", "isn't responding", "isnt responding",
            "won't respond", "wont respond",
            "not really responding",
            "won't wake up when i call", "wont wake up when i call",
            "won't wake up when i call their name", "wont wake up when i call their name",
            "won't wake when i call", "wont wake when i call",
        ]
        if any(p in t for p in unresponsive_patterns):
            return True

        if any(p in t for p in [
            "just laying there", "just lying there",
            "just lay there", "just lie there",
        ]) and any(p in t for p in [
            "not doing anything", "not really doing anything",
            "not moving much", "barely moving",
        ]):
            return True

    # 12) Expressive aphasia / brain–mouth mismatch
    if any(w in t for w in ["mouth", "speech", "talk", "speaking", "words", "word", "sentence", "sentences"]):
        brain_words = [
            "brain", "mind", "thinking", "thought", "thoughts",
            "know what i want to say", "know exactly what i want to say"
        ]
        aphasia_descriptors = [
            "not matching", "dont match", "don't match", "won't match", "wont match",
            "mixed up", "mixed-up", "mixed together",
            "tangled", "scrambled", "jumbled",
            "all wrong", "coming out wrong", "keep coming out wrong",
            "wrong words", "wrong thing", "wrong things",
            "sentences fall apart", "fall apart when i try to talk",
            "sentences keep falling apart",
            "mouth won't cooperate", "mouth wont cooperate",
            "mouth isn't listening", "mouth isnt listening",
            "mouth not doing what", "mouth isn't doing what", "mouth isnt doing what",
            "mouth won't follow", "mouth wont follow",
        ]

        if any(b in t for b in brain_words) and any(a in t for a in aphasia_descriptors):
            return True

        if "i know what i want to say" in t or "i know exactly what i want to say" in t:
            if any(a in t for a in [
                "wrong words", "coming out wrong", "mixed up", "mixed together",
                "scrambled", "tangled", "jumbled",
                "not matching", "dont match", "don't match",
            ]):
                return True

        if any(p in t for p in [
            "my brain is clear", "brain feels clear",
            "thinking totally clear", "thinking clearly", "mind is clear",
        ]):
            if any(a in t for a in aphasia_descriptors):
                return True

    return False

def _has_htn_emergent(text: str) -> bool:
    """
    Only detect true preeclampsia red flags:
      - RUQ pain OR epigastric pain
    AND at least ONE of:
      - severe headache
      - vision changes
      - strong “something is wrong” feeling

    Do NOT escalate:
      - generic pain
      - nausea/vomiting
      - itching
      - gas
      - constipation
      - breastfeeding issues
      - blood sugar checks
    """
    if not text:
        return False

    t = text.lower()

    # RUQ / Epigastric
    has_ruq = any(p in t for p in [
        "right upper quadrant pain",
        "ruq pain",
        "pain under my right ribs",
        "upper right abdominal pain",
    ])

    has_epi = any(p in t for p in [
        "epigastric pain",
        "pain in the top of my stomach",
        "pain under my ribs in the middle",
    ])

    # Severe headache ONLY (not just “headache”)
    has_severe_headache = any(p in t for p in [
        "worst headache", "severe headache", "pounding headache",
        "throbbing headache", "headache that won't go away",
    ])

    # Vision changes
    has_vision_change = any(p in t for p in [
        "blurry vision", "double vision",
        "seeing spots", "seeing stars",
        "flashing lights", "sparkles",
        "vision said dark", "vision went dark"
    ])

    # Something clearly very wrong
    has_something_wrong = any(p in t for p in [
        "something is very wrong",
        "something feels really wrong",
        "i feel like i'm dying", "i feel like i might die",
    ])

    # Core rule: RUQ or Epigastric must be present
    if not (has_ruq or has_epi):
        return False

    # At least one additional red flag
    if has_severe_headache or has_vision_change or has_something_wrong:
        return True

    return False

# =========================================================
# 1) Weighted emergent scoring safety net
# =========================================================

EMERGENT_SCORE_THRESHOLD = 6  # balanced


def compute_emergent_score(note_text: str):
    """
    Return (score, breakdown, hard_stop).

    - Caller already normalized to lowercase & stripped.
    - We will:
        * Short-circuit pure CNA/logistics requests to score=0.
        * Give big weight to true emergencies (breathing, chest, neuro, heavy bleed, etc.).
        * Keep generic "pain / hurts / cramping" very low weight.
    """
    text = (note_text or "").strip()

    score = 0
    breakdown: dict[str, int] = {}
    hard_stop = False

    def bump(label: str, points: int, condition: bool = True):
        nonlocal score
        if not condition or points == 0:
            return
        score += points
        breakdown[label] = breakdown.get(label, 0) + points

    # ------------------------------------------------------------------
    # 0) CNA-LOGISTICS OVERRIDE
    #    If this looks like a pure "help me with stuff" request and
    #    there are NO scary red-flag words, force score=0.
    # ------------------------------------------------------------------
    logistics_tokens = [
        "bathroom", "toilet", "commode",
        "help me to the bathroom", "help going to the bathroom",
        "help me to the toilet", "help going to the toilet",
        "help to the bathroom", "help to the toilet",

        "shower", "help me shower", "help into the shower",
        "help getting into the shower", "help getting to the shower",
        "help getting to the shower and back to bed",
        "help getting to the shower and back",

        "iv pole", "pole is stuck",
        "remote", "tv remote", "tv isnt working", "tv isn't working",
        "charger", "phone charger", "charge my phone",

        "fan", "blanket", "blankets", "pillow", "pillows",
        "extra gown", "gown",
        "snack", "snacks", "water", "ice", "ice chips",
        "mesh underwear", "underwear", "peri bottle", "peribottle",
        "pads", "pad", "blue pad", "chucks", "diaper", "diapers",
        "wipes", "wipe",
    ]

    # Anything here means "do NOT treat this as a pure logistics ask."
    red_flag_tokens = [
        # Breathing / color
        "cant breathe", "can't breathe", "short of breath",
        "trouble breathing", "hard to breathe", "hard time breathing",
        "wheezing", "gasping", "breathing fast",
        "blue", "purple", "grey", "gray", "ashen",

        # Chest / heart
        "chest pain", "chest hurts", "tightness in my chest",
        "heart is racing", "heart racing", "pounding in my chest",

        # Neuro
        "cant move", "can't move",
        "weakness", "weak on one side", "one side feels weak",
        "face drooping", "mouth drooping",
        "slurred speech", "words coming out wrong",
        "not making sense", "confused",
        "seizure", "seizing", "shaking i cant control", "shaking i can't control",
        "my legs keep giving out", "legs keep giving out",

        # Vision
        "vision went black", "vision went dark",
        "everything went black", "everything went dark",
        "sudden vision loss",

        # Bleeding
        "gushing", "pouring", "blood running down",
        "blood everywhere", "soaked through", "soaking through",
        "soaks through", "pad is full in", "filled my pad in",
        "bright red blood",

        # Faint / dizzy
        "about to pass out", "going to pass out", "pass out",
        "passed out", "fainted", "fainting",
        "very dizzy", "so dizzy", "dizziness", "lightheaded",

        # Really sick / infectionish
        "high fever", "really high fever",
        "shaking with chills", "rigors",

        # Strong preeclampsia type combos often caught elsewhere,
        # but keep them as red flags so we don't override.
        "worst headache of my life",
        "sudden severe headache",
    ]

    if any(tok in text for tok in logistics_tokens) and not any(tok in text for tok in red_flag_tokens):
        # Pure CNA / logistics style request => let the score be 0.
        return 0, {"cna_logistics": 0}, False

    # ------------------------------------------------------------------
    # 1) TRUE EMERGENCY BUCKETS (add weight, some also set hard_stop)
    # ------------------------------------------------------------------

    # Breathing / very scary SOB
    if any(phrase in text for phrase in [
        "cant breathe", "can't breathe",
        "cannot breathe", "can't catch my breath",
        "short of breath", "shortness of breath",
        "trouble breathing", "hard to breathe", "hard time breathing",
        "gasping", "wheezing",
    ]):
        bump("breathing", 10)
        hard_stop = True  # breathing is always treated as emergency

    # Chest pain / chest tightness
    if "chest pain" in text or "chest hurts" in text or "tightness in my chest" in text:
        bump("chest_pain", 8)
        # If also SOB, treat as hard stop
        if "short of breath" in text or "cant breathe" in text or "can't breathe" in text:
            hard_stop = True

    # Color change
    if any(phrase in text for phrase in [
        "turning blue", "turned blue",
        "turning purple", "turned purple",
        "grey", "gray", "ashen",
        "lips are blue", "face is blue",
    ]):
        bump("color_change", 9)
        hard_stop = True

    # Neuro / stroke-ish
    if any(phrase in text for phrase in [
        "cant move my arm", "can't move my arm",
        "cant move my leg", "can't move my leg",
        "legs keep giving out", "my legs keep giving out",
        "suddenly weak", "weak on one side", "one side feels weak",
        "face drooping", "one side of my face is drooping",
        "slurred speech", "words coming out wrong",
        "i know what i want to say but", "not making sense",
    ]):
        bump("neuro_weakness_speech", 9)
        hard_stop = True

    # Seizure-like
    if any(phrase in text for phrase in [
        "seizure", "seizing",
        "shaking i cant control", "shaking i can't control",
        "jerking i cant stop", "jerking i can't stop",
    ]):
        bump("seizure_like", 10)
        hard_stop = True

    # Heavy bleeding / PPH-ish
    if any(phrase in text for phrase in [
        "gushing", "pouring",
        "blood running down", "blood is running down",
        "blood everywhere",
        "soaked through", "soaking through", "soaks through",
        "pad is full in", "filled my pad in",
    ]):
        bump("heavy_bleeding", 10)
        hard_stop = True

    # Big clots
    if "clot" in text or "clots" in text:
        # rough size parsing
        if any(p in text for p in ["golf ball", "golf-ball", "bigger than a golf ball"]):
            bump("large_clots", 8)
        elif any(p in text for p in ["bigger than a quarter", "larger than a quarter"]):
            bump("large_clots", 6)
        elif any(p in text for p in ["quarter sized", "size of a quarter"]):
            bump("borderline_clots", 4)
        # small clots (dime/nickel) – basically no extra weight; classify_escalation_tier
        # already de-escalates them, so we keep it at 0 here.

    # Vision changes
    if any(phrase in text for phrase in [
        "vision went black", "vision went dark",
        "everything went black", "everything went dark",
        "sudden vision loss",
    ]):
        bump("vision_blackout", 9)
        hard_stop = True

    if any(phrase in text for phrase in [
        "seeing spots", "seeing stars", "seeing sparkles",
        "sparkles in my vision", "flashing lights",
        "very blurry vision", "really blurry vision",
    ]):
        bump("vision_spots", 5)

    # Very concerning headache cluster
    if "worst headache of my life" in text or "worst headache i've ever had" in text:
        bump("worst_headache", 8)
        hard_stop = True
    elif "headache" in text:
        if any(w in text for w in ["really bad", "very bad", "severe", "pounding", "throbbing"]):
            bump("severe_headache", 4)

    # Faint / dizzy
    if any(phrase in text for phrase in [
        "about to pass out", "going to pass out",
        "feel like i'm going to pass out", "feel like im going to pass out",
        "passed out", "fainted",
    ]):
        bump("near_syncope", 6)

    if any(phrase in text for phrase in [
        "very dizzy", "so dizzy", "extremely dizzy",
        "dizziness", "lightheaded", "light headed",
    ]):
        bump("dizzy", 4)

    # Fever + feeling very sick
    if "fever" in text or "chills" in text:
        bump("fever_chills", 3)
        if any(p in text for p in ["shaking with chills", "rigors"]):
            bump("rigors", 3)

    # BP-ish cluster (we keep this modest because you also have htn helper)
    if "blood pressure" in text or "bp " in text or text.startswith("bp"):
        if "really high" in text or "very high" in text or "so high" in text:
            bump("bp_concern", 3)
        if "headache" in text and "vision" in text:
            bump("bp_headache_vision_combo", 4)

    # Incision / wound infectionish flags (on top of what classify_escalation_tier already does)
    if any(w in text for w in ["incision", "stitches", "staples", "wound"]):
        if any(p in text for p in [
            "smells really bad", "smells bad", "foul smell", "bad smell", "odor",
            "red streaks", "red lines", "streaking up", "spreading redness",
            "pus", "oozing",
        ]):
            bump("wound_infectionish", 4)

    # Lochia infectionish flags (again, classifier already handles "no fever" reassurance)
    if "lochia" in text:
        if any(p in text for p in ["smells really bad", "smells bad", "foul smell", "bad smell"]):
            bump("lochia_odor", 4)
        if "fever" in text or "chills" in text:
            bump("lochia_fever", 4)

    # ------------------------------------------------------------------
    # 2) GENERIC PAIN / CRAMPING (KEPT LOW WEIGHT)
    # ------------------------------------------------------------------
    # We still give a *tiny* bump so a truly ugly story with lots of
    # "pain" words can push a borderline score over the line, but these
    # should NEVER make something emergent by themselves.
    if any(w in text for w in ["pain", "hurts", "hurting", "sore", "cramping", "cramps"]):
        bump("generic_pain", 1)

    return score, breakdown, hard_stop



def classify_escalation_tier(note_text: str) -> str:
    """
    Returns 'emergent' or 'routine'.

    Order:
      0) Supply-only fast path (no clinical words) -> routine
      0a) Mild headache without red flags -> routine
      0b) Mild swelling + "feel fine/okay" without red flags -> routine
      0c) Mild incision / stitches / wound concerns -> routine
      0d) Simple nausea / vomiting -> routine
      0e) Small clots (smaller than a quarter) -> routine
      0f) BP cuff / machine error only -> routine
      0g) Lochia smells odd but explicitly no fever / no heavy bleed -> routine
      0h) Asking for stronger Tylenol / meds with no red flags -> routine
      0i) Breasts very full/uncomfortable without infection red flags -> routine
      1) Existing hard-stop helpers
      2) Weighted scoring safety net
    """
    text = _normalize_text(note_text)

    if not text:
        return "routine"

        # 0) SUPPLY-ONLY FAST PATH (never emergent)
    supply_tokens = [
        # Clothing / hygiene / basic supplies
        "mesh underwear", "underwear",
        "peri bottle", "peribottle",
        "pads", "pad", "blue pad", "chucks",
        "diaper", "diapers", "wipes", "wipe",
        "blanket", "blankets", "pillow", "pillows",
        "towel", "towels",
        "extra gown", "gown",
        "socks", "non slip socks", "nonslip socks",
        "slippers",

        # Food / drink
        "snacks", "snack",
        "water", "ice", "ice chips",

        # Baby supplies / accessories
        "burp cloth", "burp clothes", "burp rag",
        "baby hat", "hat for the baby",
        "swaddle", "swaddle blanket",

        # Feeding equipment
        "formula", "bottle", "bottles",
        "pump parts", "breast pump", "pumping supplies",

        # Room / bathroom help as supply-style / CNA requests
        "bathroom", "toilet", "help to the bathroom",
        "help going to the bathroom", "help me to the bathroom",
        "help to the toilet", "help going to the toilet",
        "help me get up to pee", "help me get up to the bathroom",

        # Equipment / electronics that are *not* medical distress
        "iv pole", "pole is stuck", "pole wont roll", "pole won't roll",
        "tv remote", "remote isnt working", "remote isn't working",
        "remote not working", "tv isnt working", "tv isn't working",
        "charger", "phone charger", "charge my phone",
        "bed control", "bed wont go up", "bed won't go up",
        "bed wont go down", "bed won't go down",
        "bedside table", "tray table"
    ]

    clinical_markers = [
        "pain", "hurts", "cramp", "cramps",
        "bleeding", "blood", "clot", "clots",
        "dizzy", "dizziness", "lightheaded", "faint", "fainted",
        "short of breath", "trouble breathing", "cant breathe", "can't breathe",
        "breath", "breathing", "chest", "heart",
        "headache", "migraine",
        "vision", "blurry", "spots", "stars", "sparkles",
        "numb", "tingling",
        "swelling", "swollen", "puffy",
        "incision", "stitches", "staples", "wound",
        "fever", "chills",
        "seizure", "stroke",
    ]

    if any(tok in text for tok in supply_tokens) and not any(tok in text for tok in clinical_markers):
        # e.g. "I think I need help going to the bathroom again"
        return "routine"

    # 0a) MILD HEADACHE WITHOUT RED FLAGS -> routine
    if "headache" in text and "mild" in text:
        red_flag_headache_words = [
            "worst", "severe", "really bad", "very bad", "so bad",
            "pounding", "throbbing",
            "blurry vision", "vision", "seeing spots", "seeing stars",
            "sparkles", "flashing lights",
            "went black", "went dark", "goes black", "goes dark",
            "pass out", "passed out", "faint", "fainted", "about to pass out",
        ]
        if not any(w in text for w in red_flag_headache_words):
            return "routine"

    # 0b) MILD SWELLING + FEEL FINE/OKAY WITHOUT RED FLAGS -> routine
    if any(w in text for w in ["swollen", "swelling", "puffy"]):
        if ("a little" in text or "little" in text or "mild" in text):
            if ("feel fine" in text or "feel okay" in text or "feel ok" in text):
                red_flag_swelling_words = [
                    "got worse", "getting worse", "way worse",
                    "suddenly", "all of a sudden",
                    "really bad", "very bad",
                    "headache", "vision", "blurry", "spots", "stars",
                    "dizzy", "dizziness", "lightheaded", "faint", "pass out",
                    "short of breath", "trouble breathing", "chest", "heart",
                ]
                if not any(w in text for w in red_flag_swelling_words):
                    return "routine"

    # 0c) MILD INCISION / STITCHES / WOUND CONCERNS -> routine
    if any(w in text for w in ["incision", "stitches", "staples", "wound"]):
        incision_red_flags = [
            "bright red blood", "gushing", "pouring",
            "running down", "blood everywhere",
            "soaked", "soaking", "soaks through",
            "faint", "fainting", "about to pass out", "pass out",
            "short of breath", "trouble breathing",
            "chest", "heart",
            "vision", "blurry", "spots", "stars", "sparkles",
            "fever", "chills",
            "pus", "oozing",
            "smells bad", "smell bad", "bad smell", "odor", "odour",
            "red streaks", "red lines",
        ]
        if not any(w in text for w in incision_red_flags):
            # e.g. "The tape on my C section incision is curling up and I want someone to check it"
            return "routine"

    # 0d) SIMPLE NAUSEA / VOMITING -> routine
    if any(w in text for w in ["nausea", "nauseous", "vomit", "vomiting", "throw up", "throwing up"]):
        nausea_red_flags = [
            "blood", "bright red", "coffee ground",
            "can't keep anything down", "cant keep anything down",
            "short of breath", "trouble breathing",
            "chest", "heart",
            "faint", "fainting", "pass out", "about to pass out",
            "vision", "went black", "went dark", "goes black", "goes dark",
        ]
        if not any(w in text for w in nausea_red_flags):
            return "routine"

    # 0e) SMALL CLOTS (SMALLER THAN A QUARTER) -> routine
    if "clot" in text or "clots" in text:
        if any(p in text for p in [
            "small clots", "smaller than a quarter",
            "size of a dime", "size of a nickel",
        ]):
            return "routine"

    # 0f) BP CUFF / MACHINE ERROR ONLY -> routine
    if ("blood pressure cuff" in text or "bp cuff" in text or
        "bp machine" in text or "blood pressure machine" in text or
        ("bp" in text and "cuff" in text)):
        bp_symptom_words = [
            "dizzy", "dizziness", "lightheaded", "faint", "fainting",
            "pass out", "about to pass out",
            "chest", "heart",
            "short of breath", "trouble breathing",
            "headache", "vision", "blurry", "spots", "stars", "sparkles",
        ]
        if not any(w in text for w in bp_symptom_words):
            return "routine"

    # 0g) LOCHIA SMELLS ODD BUT NO FEVER / NO HEAVY BLEEDING -> routine
    if "lochia" in text and any(w in text for w in ["smell", "smells", "smelly", "odor", "odour", "weird"]):
        reassuring_bits = [
            "no fever", "dont have a fever", "don't have a fever",
            "no temperature", "no temp",
        ]
        heavy_bleed_flags = [
            "gushing", "pouring", "running down", "blood everywhere",
            "soaked", "soaking", "soaks through",
            "pad is full in", "filled my pad in",
            "bright red all over the pad",
        ]
        if any(r in text for r in reassuring_bits) and not any(h in text for h in heavy_bleed_flags):
            # e.g. "My lochia smells kind of weird but I dont have a fever or heavy bleeding"
            return "routine"

    # 0h) ASKING FOR STRONGER TYLENOL / MEDS WITH NO RED FLAGS -> routine
    pain_meds = ["tylenol", "acetaminophen", "ibuprofen", "motrin", "advil"]
    if any(m in text for m in pain_meds):
        if any(p in text for p in ["stronger", "isn't working", "isnt working", "not working", "doesn't work", "doesnt work"]):
            big_red_flags = [
                "chest", "heart",
                "can't breathe", "cant breathe", "short of breath", "trouble breathing",
                "faint", "fainting", "about to pass out", "pass out",
                "vision", "blurry", "spots", "stars", "sparkles",
                "gushing", "pouring", "bright red blood",
            ]
            if not any(b in text for b in big_red_flags):
                # e.g. "I feel like I need stronger Tylenol for my pain because this dose isnt working"
                return "routine"

    # 0i) BREASTS VERY FULL / UNCOMFORTABLE WITHOUT INFECTION RED FLAGS -> routine
    if "breast" in text or "breasts" in text:
        infection_flags = [
            "fever", "chills", "rigors",
            "red and hot", "red and warm",
            "very red", "bright red",
            "streak", "streaks", "red line", "red lines",
            "lump that is rock hard", "rock hard lump",
        ]
        if not any(f in text for f in infection_flags):
            return "routine"

    # 1) Existing hard-stop helpers
    if _has_heart_breath_color_emergent(text):
        return "emergent"

    if _has_neuro_emergent(text):
        return "emergent"

    if _has_htn_emergent(text):
        return "emergent"

    # 2) Weighted scoring safety net
    score, breakdown, hard_stop = compute_emergent_score(text)

    if hard_stop:
        return "emergent"

    if score >= EMERGENT_SCORE_THRESHOLD:
        return "emergent"

    return "routine"

def _is_pure_cna_supply_env(text: str) -> bool:
    """
    Return True if this sounds like a CNA / supply / environment / mobility request
    with NO major red-flag clinical markers.

    Mild pain is OK to stay CNA here (e.g. “hurts when I walk to the bathroom”).
    We ONLY block CNA if there are serious red flags.
    """
    normalized = " " + (text or "").lower().strip() + " "
    if not normalized.strip():
        return False

    # Things CNAs can handle (supplies, environment, mobility)
    supply_tokens = [
        # Supplies / comfort
        " mesh underwear ", " underwear ",
        " peri bottle ", " peribottle ",
        " pads ", " pad ", " blue pad ", " chucks ",
        " diaper ", " diapers ", " wipes ", " wipe ",
        " blanket ", " blankets ", " pillow ", " pillows ",
        " towel ", " towels ",
        " snacks ", " snack ", " water ", " ice ", " ice chips ",
        " formula ", " bottle ", " bottles ",
        " extra gown ", " gown ",

        # Bathroom / mobility
        " bathroom ", " toilet ", " restroom ",
        " help going to the bathroom ",
        " help to the bathroom ",
        " help me to the bathroom ",
        " help me to the toilet ",
        " help getting to the bathroom ",
        " help getting to the toilet ",
        " help going to the toilet ",
        " help me to the restroom ",
        " walk me to the bathroom ",
        " help me walk to the bathroom ",

        # Shower help
        " shower ",
        " help into the shower ",
        " help me into the shower ",
        " help getting into the shower ",
        " help me shower ",
        " help getting to the shower ",
        " help to the shower ",
        " help in the shower ",
        " getting to the shower and back to bed ",
        " help getting to the shower and back to bed ",

        # Equipment / environment
        " iv pole ", " iv stand ",
        " tray table ",
        " bed control ", " bed controls ",
        " tv remote ", " remote ",
        " tv isn’t working ", " tv isnt working ", " tv is not working ",
        " remote isn’t working ", " remote isnt working ", " remote is not working ",
        " charger ", " phone charger ",

        # Room comfort
        " room is cold ", " room is hot ",
        " turn the heat up ", " turn the heat down ",
        " turn the light off ", " turn the light on ",
        " lights off ", " lights on ",
        " curtain ", " curtains ",
    ]

    # TRUE RED FLAGS that should NOT be pure CNA
    red_flag_markers = [
        # Breathing / chest / heart
        " short of breath ", " trouble breathing ",
        " cant breathe ", " can't breathe ",
        " chest pain ", " chest hurts ",
        " heart is racing ", " heart is pounding ",

        # Fainting / severe dizziness
        " faint ", " fainted ", " about to pass out ", " passed out ",
        " so dizzy ", " very dizzy ",

        # Neuro / stroke-like
        " face drooping ", " drooping on one side ",
        " can’t move my arm ", " cant move my arm ",
        " can’t move my leg ", " cant move my leg ",
        " weakness on one side ", " weak on one side ",
        " slurred speech ", " can’t get my words out ", " cant get my words out ",

        # Vision changes
        " blurry vision ", " vision is blurry ", " seeing spots ",
        " seeing stars ", " sparkles in my vision ",
        " vision went black ", " vision went dark ",

        # Heavy bleeding
        " gushing blood ", " blood is gushing ",
        " pouring blood ", " bleeding a lot ",
        " blood everywhere ",
        " soaking through my pad ",
        " soaked through my pad ",
        " filling a pad ",
        " bright red blood all over ",

        # Seizure / stroke words
        " seizure ", " shaking all over ",
        " stroke ",
    ]

    # If any true red flag is present → NOT a pure CNA request
    if any(flag in normalized for flag in red_flag_markers):
        return False

    # If it contains any supply/mobility token and NO red flags → CNA is OK
    if any(tok in normalized for tok in supply_tokens):
        return True

    return False


def route_note_intelligently(note_text: str) -> str:
    """
    Decide CNA vs nurse for free-text notes.

    - Pure “supply / environment / mobility help” with *no* clinical words -> CNA
    - Anything with heart / breathing / neuro / BP red flags -> nurse
    - Everything else defaults to nurse.
    """
    # Keep it simple: just lower-case the raw text instead of using _normalize_text,
    # so we don't accidentally strip useful words.
    text = (note_text or "").lower()
    if not text.strip():
        return "nurse"

    # 1) Hard-stop clinical red flags: ALWAYS nurse
    if (
        _has_heart_breath_color_emergent(text)
        or _has_neuro_emergent(text)
        or _has_htn_emergent(text)
    ):
        return "nurse"

    # 2) Pure supply / environment / mobility help -> CNA
    supply_cna_tokens = [
        # Classic supplies
        "mesh underwear", "underwear",
        "peri bottle", "peribottle",
        "pads", "pad", "blue pad", "chucks",
        "diaper", "diapers", "wipes", "wipe",
        "blanket", "blankets", "pillow", "pillows",
        "towel", "towels",
        "snacks", "snack", "water", "ice", "ice chips",
        "formula", "bottle", "bottles",
        "extra gown", "gown",

        # Bathroom / mobility
        "bathroom", "toilet",
        "help going to the bathroom", "help to the bathroom",
        "help me to the bathroom", "help me to the toilet",
        "help getting to the bathroom", "help getting to the toilet",
        "help going to the toilet",
        "shower", "help into the shower", "help me into the shower",
        "help getting into the shower", "help me shower",
        "help getting to the shower",  # your exact test phrase pattern

        # Equipment / room environment
        "iv pole", "iv stand",
        "tray table",
        "bed control", "bed controls",
        "tv remote",
        "tv won’t turn on", "tv wont turn on", "tv is not working",
        "remote isn’t working", "remote isnt working", "remote is not working",
        "charger", "phone charger",

        # Comfort / room settings
        "room is cold", "room is hot",
        "turn the heat up", "turn the heat down",
        "turn the light off", "turn the light on",
        "lights off", "lights on",
        "curtain", "curtains",
    ]

    clinical_markers = [
        "pain", "hurts", "cramp", "cramps",
        "bleeding", "blood", "clot", "clots",
        "dizzy", "dizziness", "lightheaded", "faint", "fainted",
        "short of breath", "trouble breathing", "cant breathe", "can't breathe",
        "breath", "breathing", "chest", "heart",
        "headache", "migraine",
        "vision", "blurry", "spots", "stars", "sparkles",
        "numb", "tingling",
        "swelling", "swollen", "puffy",
        "incision", "stitches", "staples", "wound",
        "fever", "chills",
        "seizure", "stroke",
    ]

    if any(tok in text for tok in supply_cna_tokens) and not any(
        tok in text for tok in clinical_markers
    ):
        # Pure supply / environment / mobility → CNA
        return "cna"

    # 3) Anything else (clinical or ambiguous) → nurse
    return "nurse"


# --- Core Helper Functions ---
def log_to_audit_trail(event_type, details):
    try:
        now_utc = datetime.now(timezone.utc)
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    INSERT INTO audit_log (timestamp, event_type, details)
                    VALUES (:timestamp, :event_type, :details);
                """), {
                    "timestamp": now_utc,
                    "event_type": event_type,
                    "details": details
                })

        socketio.emit('new_audit_log', {
            'timestamp': now_utc.strftime('%Y-%m-%d %H:%M:%S') + ' UTC',
            'event_type': event_type,
            'details': details
        })

    except Exception as e:
        print(f"ERROR logging to audit trail: {e}")

def log_request_to_db(request_id, category, user_input, reply, room, is_first_baby):
    """
    Persist a request and emit a clear server-side debug line showing the resolved room.
    """
    try:
        # Normalize room for storage + debugging
        room_str = str(room).strip() if room is not None else None
        is_digit = room_str.isdigit() if room_str else False
        is_valid_room = is_digit and 231 <= int(room_str) <= 260

        # Helpful debug so you can see exactly what's being stored
        if is_valid_room:
            print(f"[log_request_to_db] OK  | request_id={request_id} room={room_str} role={category}")
        else:
            print(f"[log_request_to_db] WARN| request_id={request_id} invalid/unknown room='{room_str}' role={category}")

        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("""
                    INSERT INTO requests (request_id, timestamp, room, category, user_input, reply, is_first_baby)
                    VALUES (:request_id, :timestamp, :room, :category, :user_input, :reply, :is_first_baby);
                """), {
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc),
                    "room": room_str,  # store the normalized string (e.g., "241")
                    "category": category,
                    "user_input": user_input,
                    "reply": reply,
                    "is_first_baby": is_first_baby
                })

        log_to_audit_trail(
            "Request Created",
            f"Room: {room_str or 'N/A'}, Request: '{user_input}', Assigned to: {category.upper()}"
        )

    except Exception as e:
        print(f"ERROR logging to database: {e}")

def process_request(
    role,
    subject,
    user_input,
    reply_message,
    tier_override: str | None = None,
    classify_from_text: bool = True,
    from_button: bool = False,
):
    """
    Persist the request, emit dashboard updates, and (optionally) email.

    Escalation tier:
      - If tier_override is given, use that ('emergent' or 'routine').
      - Else if classify_from_text is True, use classify_escalation_tier(user_input).
      - Else default to 'routine'.

    from_button is currently just for future logging/analytics; it does not
    change behavior inside this function.
    """
    # Language-normalize the user_input for analytics/dashboards
    lang = session.get("language", "en")
    english_user_input = to_english_label(user_input, lang)

    # Unique request id
    request_id = "req_" + str(datetime.now(timezone.utc).timestamp()).replace(".", "")

    # Prefer URL ?room=... then fall back to session
    room_number = _current_room() or session.get("room_number")
    if not room_number or not _valid_room(room_number):
        room_number = None  # store as NULL/None instead of "N/A"

    is_first_baby = session.get("is_first_baby")

    # --- Decide escalation tier ---
    if tier_override is not None:
        tier = tier_override
    elif classify_from_text:
        tier = classify_escalation_tier(english_user_input)  # 'emergent' | 'routine'
    else:
        tier = "routine"

    # Write to DB in background (non-blocking)
    socketio.start_background_task(
        log_request_to_db,
        request_id,
        role,               # 'nurse' or 'cna'
        english_user_input, # normalized text for analytics
        reply_message,
        room_number,        # None if unknown/invalid
        is_first_baby,
    )

    # (Optional) email alert
    # socketio.start_background_task(
    #     send_email_alert,
    #     subject,
    #     english_user_input,
    #     room_number or "Unknown",
    # )

    # Live update to dashboards
    socketio.emit(
        "new_request",
        {
            "id": request_id,
            "room": room_number,
            "request": english_user_input,
            "role": role,  # 'nurse' | 'cna'
            "tier": tier,  # 'emergent' | 'routine'
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

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

# ---- helpers for this block ----
def _valid_room(room_str: str) -> bool:
    if not room_str or not str(room_str).isdigit():
        return False
    n = int(room_str)
    return 231 <= n <= 260

def _current_room() -> str | None:
    """
    Prefer session, but allow override via ?room=XYZ for testing.
    If a valid ?room= is passed, persist it into the session.
    """
    room = request.args.get("room") or session.get("room_number")
    if room and _valid_room(str(room)):
        room_str = str(room)
        if session.get("room_number") != room_str:
            session["room_number"] = room_str
        return room_str
    return None

def _emit_received_for(room_number: str, user_text: str, kind: str):
    """Look up the most recent matching request row and emit to the patient room."""
    if not (room_number and user_text):
        return
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT request_id, timestamp
                FROM requests
                WHERE room = :room AND user_input = :txt
                ORDER BY timestamp DESC
                LIMIT 1
            """), {"room": str(room_number), "txt": user_text}).fetchone()
        if row and row.request_id:
            emit_patient_event("request:received", room_number, {
                "request_id": row.request_id,
                "kind": kind,  # "note" or "option"
                "note": user_text if kind == "note" else "",
                "created_at": (row.timestamp or datetime.now(timezone.utc)).isoformat()
            })
    except Exception as e:
        print(f"WARN: could not emit request:received for room {room_number}: {e}")

@app.route("/chat", methods=["GET", "POST"])
def handle_chat():
    # --- Resolve pathway: allow URL override, otherwise honor existing session ---
    qp = (request.args.get("pathway") or "").strip().lower()
    if qp in ("standard", "bereavement"):
        session["pathway"] = qp

    pathway = session.get("pathway", "standard")
    lang = session.get("language", "en")

    # Load the correct button config module based on pathway + language
    config_module_name = (
        f"button_config_bereavement_{lang}"
        if pathway == "bereavement"
        else f"button_config_{lang}"
    )
    try:
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data
    except (ImportError, AttributeError) as e:
        print(f"ERROR: Could not load configuration module '{config_module_name}'. Error: {e}")
        return (
            f"Error: Configuration file '{config_module_name}.py' is missing or invalid. "
            "Please contact support."
        )

    # Resolve room number from ?room=, session, or POST
    room_number = _current_room()

    # If POST carried a room value, persist it (works even if the URL lacks ?room=)
    room_from_form = (request.form.get("room") or "").strip() if request.method == "POST" else ""
    if room_from_form and _valid_room(room_from_form):
        session["room_number"] = room_from_form
        room_number = room_from_form

    # Keep session in sync with the resolved room
    if room_number and session.get("room_number") != room_number:
        session["room_number"] = room_number

    if request.method == "POST":
        # ===========================================
        # 1) Free-text note path  (CUSTOM NOTE BOX)
        #    -> emergent scoring is ALLOWED here
        # ===========================================
        if request.form.get("action") == "send_note":
            note_text = (request.form.get("custom_note") or "").strip()
            if note_text:
                # Decide nurse vs CNA based on the text (uses emergent logic)
                role = route_note_intelligently(note_text)  # "nurse" or "cna"
                reply_message = button_data.get(f"{role}_notification", "Your request has been sent.")

                # Persist + notify (free-text: allow classifier)
                session["reply"] = process_request(
                    role=role,
                    subject="Custom Patient Note",
                    user_input=note_text,
                    reply_message=reply_message,
                    tier_override=None,          # let classifier decide emergent vs routine
                    classify_from_text=True,     # ✅ FREE TEXT gets scored
                    from_button=False,
                )
                session["options"] = button_data["main_buttons"]

                # Notify patient page that the request was received
                if room_number:
                    _emit_received_for(room_number, note_text, kind="note")
            else:
                session["reply"] = button_data.get("empty_custom_note", "Please type a message in the box.")
                session["options"] = button_data["main_buttons"]

        # ===========================================
        # 2) Button click path
        #    -> NO emergent scoring, except explicit emergency button
        # ===========================================
        else:
            user_input = (request.form.get("user_input") or "").strip()
            back_text = button_data.get("back_text", "⬅ Back")

            # ----------------------------
            # HARD-CODED EMERGENCY BUTTON
            # "I'm having an emergency" should ALWAYS:
            #   - route to nurse
            #   - be tier='emergent'
            # ----------------------------
            if user_input == "I'm having an emergency":
                request_text = "Patient pressed EMERGENCY button: 'I'm having an emergency'."
                session["reply"] = process_request(
                    role="nurse",
                    subject="EMERGENCY – patient pressed emergency button",
                    user_input=request_text,
                    reply_message=button_data.get("nurse_notification", "Your nurse has been notified."),
                    tier_override="emergent",   # ✅ FORCE emergent
                    classify_from_text=False,   # don't re-score text
                    from_button=True,
                )
                session["options"] = button_data["main_buttons"]
                if room_number:
                    _emit_received_for(room_number, request_text, kind="option")

            # ----------------------------
            # SPECIAL FLOW: Shower follow-up
            # ----------------------------
            elif user_input == "Can I take a shower?":
                session["reply"] = (
                    "Usually yes — but please check with your nurse if you have an IV, "
                    "had a C-section, or have special instructions."
                )
                session["options"] = [
                    "Ask my nurse about taking a shower",
                    "Got it, I'll wait for now",
                ]
                if back_text not in session["options"]:
                    session["options"].append(back_text)

            elif user_input == "Ask my nurse about taking a shower":
                request_text = "Patient would like to ask about taking a shower."
                session["reply"] = process_request(
                    role="nurse",
                    subject="Shower permission request",
                    user_input=request_text,
                    reply_message=button_data.get("nurse_notification", "Your request has been sent."),
                    tier_override=None,        # nurse, but not emergent
                    classify_from_text=False,  # ✅ BUTTON: no emergent scoring
                    from_button=True,
                )
                session["options"] = button_data["main_buttons"]
                if room_number:
                    _emit_received_for(room_number, request_text, kind="option")

            elif user_input == "Got it, I'll wait for now":
                session["reply"] = "Okay — if you change your mind, just let me know anytime."
                session["options"] = button_data["main_buttons"]

            # ----------------------------
            # Back / Home
            # ----------------------------
            elif user_input == back_text:
                session.pop("reply", None)
                session.pop("options", None)
                return redirect(url_for("handle_chat", room=room_number) if room_number else url_for("handle_chat"))

            # ----------------------------
            # Standard known-button handling via button_data
            # ALL of these should be NON-emergent
            # ----------------------------
            elif user_input in button_data:
                button_info = button_data[user_input]
                session["reply"] = button_info.get("question") or button_info.get("note", "")
                session["options"] = button_info.get("options", [])

                if session["options"] and back_text not in session["options"]:
                    session["options"].append(back_text)
                elif not session["options"]:
                    session["options"] = button_data["main_buttons"]

                # Action button -> notify CNA/Nurse + log
                if "action" in button_info:
                    action = button_info["action"]
                    role = "cna" if action == "Notify CNA" else "nurse"
                    subject = f"{role.upper()} Request"
                    notification_message = button_info.get(
                        "note",
                        button_data.get(f"{role}_notification", "Your request has been sent.")
                    )

                    # BUTTON request: NEVER emergent via classifier
                    session["reply"] = process_request(
                        role=role,
                        subject=subject,
                        user_input=user_input,
                        reply_message=notification_message,
                        tier_override=None,        # no forced emergent
                        classify_from_text=False,  # ✅ BUTTON: no emergent scoring
                        from_button=True,
                    )
                    session["options"] = button_data["main_buttons"]

                    if room_number:
                        _emit_received_for(room_number, user_input, kind="option")

            # ----------------------------
            # Unknown input
            # ----------------------------
            else:
                session["reply"] = button_data.get(
                    "fallback_unrecognized",
                    "I'm sorry, I didn't understand that. Please use the buttons provided.",
                )
                session["options"] = button_data["main_buttons"]

        # Always redirect after POST (PRG)
        return redirect(url_for("handle_chat", room=room_number) if room_number else url_for("handle_chat"))

    # --- GET: render page ---
    reply = session.pop("reply", button_data["greeting"])
    options = session.pop("options", button_data["main_buttons"])
    return render_template(
        "chat.html",
        reply=reply,
        options=options,
        button_data=button_data,
        room_number=room_number,  # used by chat.html Socket.IO connect
    )

@app.route("/reset-language")
def reset_language():
    """
    Clear only language-related state so the patient can re-choose a language,
    but KEEP room_number and pathway intact.
    """
    session.pop("language", None)
    session.pop("is_first_baby", None)  # so standard pathway re-asks the question
    session.pop("reply", None)          # clear any old reply text
    session.pop("options", None)        # clear old button set

    return redirect(url_for("language_selector"))
    
@app.route("/dashboard")
def dashboard():
    active_requests = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT
                    COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                    room,
                    user_input,
                    category AS role,
                    timestamp
                FROM requests
                WHERE completion_timestamp IS NULL
                ORDER BY timestamp DESC;
            """))

            for row in result:
                # Decide escalation tier for dashboard
                text_for_tier = (row.user_input or "").strip().lower()

                if "patient pressed emergency button" in text_for_tier:
                    tier = "emergent"
                else:
                    tier = classify_escalation_tier(text_for_tier)

                active_requests.append({
                    "id": row.request_id,
                    "room": row.room,
                    "request": row.user_input,
                    "role": row.role,
                    "tier": tier,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                })

    except Exception as e:
        print(f"ERROR fetching active requests: {e}")

    return render_template("dashboard.html",
                           active_requests=active_requests,
                           nurse_context=False)


# --- Analytics ---
@app.route('/analytics')
def analytics():
    avg_response_time = "N/A"
    top_requests_labels, top_requests_values = [], []
    most_requested_labels, most_requested_values = [], []
    requests_by_hour_labels, requests_by_hour_values = [], []
    first_baby_labels, first_baby_values = [], []
    multi_baby_labels, multi_baby_values = [], []
    try:
        with engine.connect() as connection:
            avg_time_result = connection.execute(text("""
                SELECT AVG(EXTRACT(EPOCH FROM (completion_timestamp - timestamp))) as avg_seconds
                FROM requests
                WHERE completion_timestamp IS NOT NULL;
            """)).scalar_one_or_none()
            if avg_time_result is not None:
                minutes, seconds = divmod(int(avg_time_result), 60)
                avg_response_time = f"{minutes}m {seconds}s"

            top_requests_result = connection.execute(text("""
                SELECT category, COUNT(id) FROM requests
                GROUP BY category
                ORDER BY COUNT(id) DESC;
            """)).fetchall()
            top_requests_labels = [row[0] for row in top_requests_result]
            top_requests_values = [row[1] for row in top_requests_result]

            most_requested_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests
                GROUP BY user_input
                ORDER BY count DESC
                LIMIT 5;
            """)).fetchall()
            most_requested_labels = [row[0] for row in most_requested_result]
            most_requested_values = [row[1] for row in most_requested_result]

            requests_by_hour_result = connection.execute(text("""
                SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(id)
                FROM requests
                GROUP BY hour
                ORDER BY hour;
            """)).fetchall()
            hourly_counts = defaultdict(int)
            for hour, count in requests_by_hour_result:
                hourly_counts[int(hour)] = count
            requests_by_hour_labels = [f"{h}:00" for h in range(24)]
            requests_by_hour_values = [hourly_counts[h] for h in range(24)]

            first_baby_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests
                WHERE is_first_baby IS TRUE
                GROUP BY user_input
                ORDER BY count DESC
                LIMIT 5;
            """)).fetchall()
            first_baby_labels = [row[0] for row in first_baby_result]
            first_baby_values = [row[1] for row in first_baby_result]

            multi_baby_result = connection.execute(text("""
                SELECT user_input, COUNT(id) as count
                FROM requests
                WHERE is_first_baby IS FALSE
                GROUP BY user_input
                ORDER BY count DESC
                LIMIT 5;
            """)).fetchall()
            multi_baby_labels = [row[0] for row in multi_baby_result]
            multi_baby_values = [row[1] for row in multi_baby_result]
    except Exception as e:
        print(f"ERROR fetching analytics data: {e}")

    return render_template(
        'analytics.html',
        avg_response_time=avg_response_time,
        top_requests_labels=top_requests_labels,
        top_requests_values=top_requests_values,
        most_requested_labels=most_requested_labels,
        most_requested_values=most_requested_values,
        requests_by_hour_labels=requests_by_hour_labels,
        requests_by_hour_values=requests_by_hour_values,
        first_baby_labels=first_baby_labels,
        first_baby_values=first_baby_values,
        multi_baby_labels=multi_baby_labels,
        multi_baby_values=multi_baby_values
    )

# --- Assignments (shift-aware; CNA zones; strict nurse filtering) ---
@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    today = date.today()

    # Normalize the shift (default day)
    if request.method == 'GET':
        shift = (request.args.get('shift') or 'day').lower()
    else:
        shift = (request.form.get('shift') or 'day').lower()
    if shift not in ('day', 'night'):
        shift = 'day'

    # ---------- Load nurses grouped by preferred_shift ----------
    nurses_by_shift = {'day': [], 'night': [], 'unspecified': []}
    preferred_nurses, other_nurses, opposite_nurses = [], [], []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT
                    name,
                    CASE
                      WHEN preferred_shift IS NULL OR TRIM(preferred_shift) = '' THEN 'unspecified'
                      ELSE LOWER(TRIM(BOTH '''' FROM preferred_shift))
                    END AS pref
                FROM staff
                WHERE LOWER(role) = 'nurse'
                ORDER BY name;
            """)).fetchall()

        for name, pref in rows:
            if not name or name.strip().lower() == 'unassigned':
                continue
            if pref not in ('day', 'night'):
                pref = 'unspecified'
            nurses_by_shift[pref].append(name)

        preferred_nurses = sorted(nurses_by_shift.get(shift, []))
        other_nurses = sorted(nurses_by_shift.get('unspecified', []))
        opp = 'night' if shift == 'day' else 'day'
        opposite_nurses = sorted(nurses_by_shift.get(opp, []))
    except Exception:
        preferred_nurses, other_nurses, opposite_nurses = [], [], []

    # ---------- Save (POST) ----------
    if request.method == 'POST':
        # 1) Save nurse-by-room (own transaction)
        try:
            with engine.connect() as connection:
                with connection.begin():
                    for room_number in ALL_ROOMS:
                        staff_name = request.form.get(f'nurse_for_room_{room_number}')
                        if staff_name and staff_name != 'unassigned':
                            connection.execute(text("""
                                INSERT INTO assignments (assignment_date, shift, room_number, staff_name)
                                VALUES (:date, :shift, :room, :nurse)
                                ON CONFLICT (assignment_date, shift, room_number)
                                DO UPDATE SET staff_name = EXCLUDED.staff_name;
                            """), {"date": today, "shift": shift, "room": room_number, "nurse": staff_name})
                        else:
                            connection.execute(text("""
                                DELETE FROM assignments
                                WHERE assignment_date = :date
                                  AND shift = :shift
                                  AND room_number = :room;
                            """), {"date": today, "shift": shift, "room": room_number})
        except Exception as e:
            print(f"ERROR saving nurse assignments: {e}")

        # 2) Save CNA coverage (separate transaction; DELETE→INSERT)
        try:
            cna_front_form = request.form.get('cna_front', 'unassigned')
            cna_back_form  = request.form.get('cna_back',  'unassigned')
            cna_front_db = None if cna_front_form == 'unassigned' else cna_front_form
            cna_back_db  = None if cna_back_form  == 'unassigned' else cna_back_form

            with engine.connect() as connection:
                with connection.begin():
                    for zone, name in [('front', cna_front_db), ('back', cna_back_db)]:
                        connection.execute(text("""
                            DELETE FROM cna_coverage
                            WHERE assignment_date = :date AND shift = :shift AND zone = :zone;
                        """), {"date": today, "shift": shift, "zone": zone})
                        connection.execute(text("""
                            INSERT INTO cna_coverage (assignment_date, shift, zone, cna_name)
                            VALUES (:date, :shift, :zone, :name);
                        """), {"date": today, "shift": shift, "zone": zone, "name": name})
        except Exception as e:
            # Don't roll back nurse saves if CNA write fails
            print(f"ERROR saving CNA coverage (ignored): {e}")

        return redirect(url_for('assignments', shift=shift))

    # ---------- Load CNAs for dropdown ----------
    all_cnas = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT name
                FROM staff
                WHERE LOWER(role) = 'cna'
                ORDER BY name;
            """)).fetchall()
            all_cnas = [r[0] for r in rows if r[0] and r[0].strip().lower() != 'unassigned']
    except Exception as e:
        print(f"ERROR fetching CNAs: {e}")

    # ---------- Read back today's nurse assignments for this shift ----------
    current_assignments = {}
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT room_number, staff_name
                FROM assignments
                WHERE assignment_date = :date AND shift = :shift;
            """), {"date": today, "shift": shift}).fetchall()
            for r in rows:
                current_assignments[r.room_number] = r[1] if isinstance(r, tuple) else r.staff_name
    except Exception as e:
        print(f"ERROR fetching assignments: {e}")

    # ---------- Read back today's CNA coverage for this shift ----------
    cna_front_val, cna_back_val = 'unassigned', 'unassigned'
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT zone, cna_name
                FROM cna_coverage
                WHERE assignment_date = :date AND shift = :shift;
            """)).fetchall()
            zmap = {(r[0] or '').lower(): r[1] for r in rows}
            cna_front_val = zmap.get('front') or 'unassigned'
            cna_back_val  = zmap.get('back')  or 'unassigned'
    except Exception as e:
        print(f"INFO fetching CNA coverage: {e}")

    # ---------- Render ----------
    return render_template(
        'assignments.html',
        all_rooms=ALL_ROOMS,
        preferred_nurses=preferred_nurses,
        other_nurses=other_nurses,
        opposite_nurses=opposite_nurses,
        current_assignments=current_assignments,
        all_cnas=all_cnas,
        cna_front=cna_front_val,
        cna_back=cna_back_val,
        shift=shift
    )

@app.route('/room/reset', methods=['POST'])
def room_reset():
    """Mark a room as 'reset' (new patient) and clear its nurse assignment for today's selected shift."""
    try:
        today = date.today()
        shift = (request.form.get('shift') or 'day').lower()
        room = (request.form.get('room') or '').strip()

        if shift not in ('day', 'night') or not room:
            return redirect(url_for('assignments', shift=shift or 'day'))

        with engine.connect() as connection:
            with connection.begin():
                # 1) Upsert room_state (preserve existing tags, bump reset_at)
                connection.execute(text("""
                    INSERT INTO room_state (assignment_date, shift, room_number, reset_at, tags)
                    VALUES (:d, :s, :r, NOW(),
                        COALESCE((SELECT tags FROM room_state
                                  WHERE assignment_date = :d AND shift = :s AND room_number = :r),
                                 '[]'))
                    ON CONFLICT (assignment_date, shift, room_number)
                    DO UPDATE SET reset_at = EXCLUDED.reset_at;
                """), {"d": today, "s": shift, "r": room})

                # 2) Clear any nurse assignment for this room/shift/date
                connection.execute(text("""
                    DELETE FROM assignments
                    WHERE assignment_date = :d AND shift = :s AND room_number = :r;
                """), {"d": today, "s": shift, "r": room})

        return redirect(url_for('assignments', shift=shift))

    except Exception as e:
        print(f"ERROR in /room/reset: {e}")
        # Fall back to whatever shift was posted, defaulting to day
        return redirect(url_for('assignments', shift=(request.form.get('shift') or 'day').lower()))

@app.route('/manager-dashboard', methods=['GET', 'POST'])
def manager_dashboard():
    if not session.get('manager_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        try:
            with engine.connect() as connection:
                with connection.begin():
                    if action == 'add_staff':
                        # Read & normalize inputs
                        name = (request.form.get('name') or '').strip()
                        role = (request.form.get('role') or 'nurse').strip().lower()
                        if role not in ('nurse', 'cna'):
                            role = 'nurse'

                        # '', 'unspecified', None => store as NULL
                        pref_raw = (request.form.get('preferred_shift') or '').strip().lower()
                        preferred_shift = pref_raw if pref_raw in ('day', 'night') else None

                        if name:
                            # Upsert on name so edits are easy from the UI
                            connection.execute(text("""
                                INSERT INTO staff (name, role, preferred_shift)
                                VALUES (:name, :role, :preferred_shift)
                                ON CONFLICT (name) DO UPDATE
                                SET role = EXCLUDED.role,
                                    preferred_shift = EXCLUDED.preferred_shift;
                            """), {
                                "name": name,
                                "role": role,
                                "preferred_shift": preferred_shift
                            })

                            log_to_audit_trail(
                                "Staff Added",
                                f"Added/updated staff: {name} ({role}, pref_shift={preferred_shift or 'unspecified'})"
                            )

                    elif action == 'remove_staff':
                        staff_id = request.form.get('staff_id')
                        if staff_id:
                            staff_member = connection.execute(
                                text("SELECT name, role FROM staff WHERE id = :id;"),
                                {"id": staff_id}
                            ).first()

                            connection.execute(
                                text("DELETE FROM staff WHERE id = :id;"),
                                {"id": staff_id}
                            )

                            if staff_member:
                                log_to_audit_trail(
                                    "Staff Removed",
                                    f"Removed staff member: {staff_member.name} ({staff_member.role})"
                                )

                    elif action == 'set_pin':
                        # Set/reset a per-nurse PIN (hashed)
                        staff_id = request.form.get('staff_id')
                        new_pin  = (request.form.get('new_pin') or '').strip()

                        if staff_id and new_pin and new_pin.isdigit() and len(new_pin) >= 4:
                            try:
                                pin_hash = generate_password_hash(new_pin)
                                connection.execute(text("""
                                    UPDATE staff
                                    SET pin_hash = :pin_hash,
                                        pin_set_at = NOW()
                                    WHERE id = :id;
                                """), {"pin_hash": pin_hash, "id": staff_id})

                                log_to_audit_trail("PIN Set", f"Manager set/reset PIN for staff_id={staff_id}")
                            except Exception as e:
                                print(f"ERROR setting PIN: {e}")
                        else:
                            print("WARN set_pin: invalid staff_id/new_pin")

                    elif action == 'clear_pin':
                        staff_id = request.form.get('staff_id')
                        if staff_id:
                            try:
                                connection.execute(text("""
                                    UPDATE staff
                                    SET pin_hash = NULL,
                                        pin_set_at = NULL
                                    WHERE id = :id;
                                """), {"id": staff_id})
                                log_to_audit_trail("PIN Cleared", f"Manager cleared PIN for staff_id={staff_id}")
                            except Exception as e:
                                print(f"ERROR clearing PIN: {e}")
                        else:
                            print("WARN clear_pin: missing staff_id")

        except Exception as e:
            print(f"ERROR updating staff: {e}")

        return redirect(url_for('manager_dashboard'))

    # ----- GET: fetch staff + recent audit log -----
    staff_list = []
    audit_log = []
    try:
        with engine.connect() as connection:
            # include pin_set_at so UI can show if a PIN exists
            staff_result = connection.execute(text("""
                SELECT id, name, role, preferred_shift, pin_set_at
                FROM staff
                ORDER BY name;
            """))
            staff_list = staff_result.fetchall()

            audit_result = connection.execute(text("""
                SELECT timestamp, event_type, details
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT 50;
            """))
            audit_log = audit_result.fetchall()
    except Exception as e:
        print(f"ERROR fetching manager dashboard data: {e}")

    return render_template('manager_dashboard.html', staff=staff_list, audit_log=audit_log)

# --- Staff Portal (pilot PIN) -----------------------------------------------
def _infer_shift_now() -> str:
    """Return 'day' from 07:00–18:59, else 'night'."""
    now = datetime.now()
    return 'day' if time(7, 0) <= now.time() < time(19, 0) else 'night'

@app.route('/staff-portal', methods=['GET', 'POST'])
def staff_portal():
    """
    Pilot login: optional env-wide PIN (STAFF_PORTAL_PIN) + nurse name select.
    """
    pin_required = os.getenv("STAFF_PORTAL_PIN")
    prior_name = None

    if request.method == 'POST':
        entered_pin = (request.form.get('pin') or '').strip()
        staff_name  = (request.form.get('staff_name') or '').strip()
        prior_name = staff_name

        # If a PIN is configured, require it (pilot-simple)
        if pin_required and entered_pin != pin_required:
            flash("Invalid PIN.", "danger")
        elif not staff_name:
            flash("Please enter your name.", "danger")
        else:
            # Success → send to nurse dashboard (shift inferred there)
            shift = _infer_shift_now()
            return redirect(url_for('staff_dashboard_for_nurse', staff_name=staff_name, shift=shift))

    # For GET or failed POST, load nurse names for the dropdown
    nurse_names = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT name
                FROM staff
                WHERE LOWER(role) = 'nurse'
                ORDER BY name;
            """)).fetchall()
            nurse_names = [r[0] for r in rows if r[0]]
    except Exception as e:
        print(f"ERROR loading nurse names for staff portal: {e}")

    return render_template(
        'staff_portal.html',
        nurse_names=nurse_names,
        pin_required=bool(pin_required),
        prior_name=prior_name
    )

@app.route('/staff/dashboard/<staff_name>')
def staff_dashboard_for_nurse(staff_name):
    """
    Nurse dashboard:
      - scope=mine (default): only this nurse's rooms (today+shift)
      - scope=all: all active requests (to help others)
      - shift=day|night (defaults based on current time)
    """
    today = date.today()

    # Shift param or inferred
    shift = (request.args.get('shift') or _infer_shift_now()).strip().lower()
    if shift not in ('day', 'night'):
        shift = 'day'

    # Scope: 'mine' (default) or 'all'
    scope = (request.args.get('scope') or 'mine').strip().lower()
    if scope not in ('mine', 'all'):
        scope = 'mine'

    # Rooms assigned to this nurse for TODAY + SHIFT
    rooms_for_nurse = []
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT room_number
                FROM assignments
                WHERE assignment_date = :d
                  AND shift = :s
                  AND staff_name = :n
                ORDER BY room_number;
            """), {"d": today, "s": shift, "n": staff_name}).fetchall()
            rooms_for_nurse = [r[0] for r in rows]
    except Exception as e:
        print(f"ERROR fetching rooms for nurse {staff_name}: {e}")

    # Active requests (mine or all)
    active_requests = []
    try:
        with engine.connect() as connection:
            if scope == 'all':
                q = text("""
                    SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                        room, user_input, category as role, timestamp

                    FROM requests
                    WHERE completion_timestamp IS NULL
                    ORDER BY timestamp DESC;
                """)
                result = connection.execute(q)
            else:
                if rooms_for_nurse:
                    q = text("""
                        SELECT COALESCE(request_id, CAST(id AS VARCHAR)) AS request_id,
                            room, user_input, category as role, timestamp

                        FROM requests
                        WHERE completion_timestamp IS NULL
                          AND room = ANY(:room_list)
                        ORDER BY timestamp DESC;
                    """)
                    result = connection.execute(q, {"room_list": rooms_for_nurse})
                else:
                    result = []

            for row in result:
                active_requests.append({
                    'id': row.request_id,
                    'room': row.room,
                    'request': row.user_input,
                    'role': row.role,
                    'timestamp': row.timestamp.isoformat() if row.timestamp else None
                })
    except Exception as e:
        print(f"ERROR fetching nurse dashboard requests: {e}")

    # Build toggle/link URLs for the template
    next_scope = 'all' if scope == 'mine' else 'mine'
    toggle_url = url_for('staff_dashboard_for_nurse',
                         staff_name=staff_name, shift=shift, scope=next_scope)
    day_url   = url_for('staff_dashboard_for_nurse',
                        staff_name=staff_name, shift='day', scope=scope)
    night_url = url_for('staff_dashboard_for_nurse',
                        staff_name=staff_name, shift='night', scope=scope)

    return render_template(
        "dashboard.html",
        active_requests=active_requests,
        nurse_context=True,          # template uses this to switch headings/links
        nurse_name=staff_name,
        nurse_rooms=rooms_for_nurse, # rendered as chips
        shift=shift,
        scope=scope,
        day_url=day_url,
        night_url=night_url,
        toggle_url=toggle_url
    )

@app.get("/debug/ping_patient")
def debug_ping_patient():
    room = request.args.get("room", "").strip()
    status = request.args.get("status", "ack").strip().lower()  # ack|omw|asap
    if not _valid_room(room):
        return jsonify({"ok": False, "error": "invalid room"}), 400
    emit_patient_event("request:status", room, {
        "request_id": "debug",
        "status": status,
        "nurse": "Debug",
        "ts": datetime.now(timezone.utc).isoformat()
    })
    return jsonify({"ok": True, "room": room, "status": status})

@app.route('/api/active_requests')
def api_active_requests():
    """JSON: returns active requests for manager or for a nurse's scope."""
    today = date.today()
    staff_name = (request.args.get('staff_name') or '').strip()
    shift = (request.args.get('shift') or '').strip().lower()
    scope = (request.args.get('scope') or '').strip().lower()

    # Defaults: manager view shows all
    if shift not in ('day', 'night'):
        shift = None  # ignore shift unless staff_name provided
    if scope not in ('mine', 'all'):
        scope = 'all'

    active_requests = []

    try:
        with engine.connect() as connection:
            if staff_name:
                # Nurse view
                # 1) rooms for nurse (today + shift)
                rooms_for_nurse = []
                if shift:
                    rrows = connection.execute(text("""
                        SELECT room_number
                        FROM assignments
                        WHERE assignment_date = :d
                          AND shift = :s
                          AND staff_name = :n
                        ORDER BY room_number;
                    """), {"d": today, "s": shift, "n": staff_name}).fetchall()
                    rooms_for_nurse = [r[0] for r in rrows]

                if scope == 'mine':
                    # Only my rooms
                    if rooms_for_nurse:
                        res = connection.execute(text("""
                            SELECT request_id, room, user_input, category as role, timestamp
                            FROM requests
                            WHERE completion_timestamp IS NULL
                              AND room = ANY(:room_list)
                            ORDER BY timestamp DESC;
                        """), {"room_list": rooms_for_nurse})
                    else:
                        res = []
                else:
                    # 'all' for nurse view
                    res = connection.execute(text("""
                        SELECT request_id, room, user_input, category as role, timestamp
                        FROM requests
                        WHERE completion_timestamp IS NULL
                        ORDER BY timestamp DESC;
                    """))
            else:
                # Manager view: all active
                res = connection.execute(text("""
                    SELECT request_id, room, user_input, category as role, timestamp
                    FROM requests
                    WHERE completion_timestamp IS NULL
                    ORDER BY timestamp DESC;
                """))

            for row in res:
                active_requests.append({
                    "id": row.request_id,
                    "room": row.room,
                    "request": row.user_input,
                    "role": row.role,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None
                })

    except Exception as e:
        print(f"/api/active_requests error: {e}")
        return jsonify({"error": "fetch_failed"}), 500

    return jsonify({"active_requests": active_requests})

@app.route("/debug/assignments_today")
def debug_assignments_today():
    """Quick snapshot of today's assignments for BOTH shifts."""
    from datetime import date
    rows = []
    try:
        with engine.connect() as connection:
            res = connection.execute(text("""
                SELECT assignment_date, shift, room_number, staff_name
                FROM assignments
                WHERE assignment_date = :d
                ORDER BY shift, room_number;
            """), {"d": date.today()}).fetchall()
            rows = [dict(assignment_date=str(r[0]),
                         shift=r[1],
                         room=r[2],
                         staff=r[3]) for r in res]
    except Exception as e:
        return jsonify({"error": f"query_failed: {e.__class__.__name__}: {e}"}), 500
    return jsonify({"count": len(rows), "rows": rows})

# --- SocketIO Event Handlers ---

def emit_patient_event(event: str, room_number: str | int, payload: dict):
    """Emit an event to the patient's socket.io room."""
    socketio.emit(
        event,
        {"room_id": str(room_number), **(payload or {})},
        to=f"patient:{room_number}",
        namespace="/patient",
    )

def _get_room_for_request(request_id: str | int) -> str | None:
    """Look up room number for a given request_id from the requests table."""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT room FROM requests WHERE request_id = :rid LIMIT 1"),
                {"rid": request_id},
            ).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception as e:
        print(f"ERROR reading room for request {request_id}: {e}")
    return None

# --- Patient namespace: connect first, then join via 'patient:join' ---
@socketio.on("connect", namespace="/patient")
def patient_connect():
    """
    Do not reject the connection here; some proxies race the query args.
    We will join the room when the client sends 'patient:join'.
    """
    try:
        # If query has room_id and it's valid, we can eagerly join as well.
        room_id = (request.args.get("room_id") or "").strip()
        if _valid_room(room_id):
            join_room(f"patient:{room_id}", namespace="/patient")
            # Optional: tell client we auto-joined
            socketio.emit("patient:joined", {"room_id": room_id}, namespace="/patient")
    except Exception as e:
        print(f"[patient] connect error: {e}")

@socketio.on("patient:join", namespace="/patient")
def patient_join(data):
    """Explicit join from the client after connect/reconnect."""
    try:
        room_id = str(data.get("room_id", "")).strip()
        if _valid_room(room_id):
            join_room(f"patient:{room_id}", namespace="/patient")
            socketio.emit("patient:joined", {"room_id": room_id}, to=f"patient:{room_id}", namespace="/patient")
        else:
            # Notify this socket that the room id was invalid (no join).
            socketio.emit("patient:error", {"error": "invalid_room", "room_id": room_id}, namespace="/patient")
    except Exception as e:
        print(f"[patient] join error: {e}")
        socketio.emit("patient:error", {"error": "join_exception"}, namespace="/patient")

@socketio.on("disconnect", namespace="/patient")
def patient_disconnect(reason=None):
    # You can keep your logging and also see the reason if it's provided
    print("[patient] client disconnected", f"reason={reason!r}")

# --- Default error logger for any namespace/event ---
@socketio.on_error_default
def default_error_handler(e):
    print(f"[socketio] error: {e}")

# --- (kept) generic join for dashboards/other rooms ---
@socketio.on("join")
def on_join(data):
    room = data.get("room")
    if room:
        join_room(room)

@socketio.on("acknowledge_request")
def handle_acknowledge(data):
    """
    Accepts both new and legacy payloads.
    """
    try:
        print("\n[acknowledge_request] IN:", data)

        # 1) dashboard broadcast (if you still use it)
        dash_room = data.get("room")
        if dash_room and "message" in data:
            socketio.emit("status_update", {"message": data["message"]}, to=dash_room)

        # 2) patient room
        room_number = data.get("room_number")
        if not room_number:
            reqid = data.get("request_id")
            if reqid:
                room_number = _get_room_for_request(reqid)
            if not room_number and dash_room and _valid_room(str(dash_room)):
                room_number = str(dash_room)

        # 3) status
        status = (data.get("status") or "").lower().strip()
        if status not in ("ack", "omw", "asap"):
            msg = (data.get("message") or "").lower()
            if "ack" in msg or "received" in msg:
                status = "ack"
            elif "on my way" in msg or "on the way" in msg:
                status = "omw"
            elif "asap" in msg or "another room" in msg or "soon as" in msg:
                status = "asap"
            else:
                status = "ack"

        # 4) role
        role = (data.get("role") or "nurse").lower().strip()
        if role not in ("nurse", "cna"):
            role = "nurse"

        print(f"[acknowledge_request] RESOLVED room={room_number} status={status} role={role}")

        # 5) emit to patient
        if room_number and _valid_room(str(room_number)):
            payload = {
                "request_id": data.get("request_id"),
                "status": status,             # "ack" | "omw" | "asap"
                "nurse": data.get("nurse_name"),
                "role": role,                 # "nurse" | "cna"
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            print(f"[acknowledge_request] EMIT to patient:{room_number} -> request:status {payload}")
            emit_patient_event("request:status", room_number, payload)
        else:
            print(f"[acknowledge_request] SKIP emit — invalid or missing room: {room_number}")
    except Exception as e:
        print(f"[acknowledge_request] ERROR: {e}")

# "Defer" (re-route to nurse) — dashboard only (no patient message)
@socketio.on("defer_request")
def handle_defer_request(data):
    request_id = data.get("id")
    if not request_id:
        return
    now_utc = datetime.now(timezone.utc)
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(
                    text("""
                        UPDATE requests
                        SET category = 'nurse', deferral_timestamp = :now
                        WHERE request_id = :request_id;
                    """),
                    {"now": now_utc, "request_id": request_id},
                )
        socketio.emit(
            "request_updated",
            {"id": request_id, "new_role": "nurse", "new_timestamp": now_utc.isoformat()},
        )
        log_to_audit_trail("Request Deferred", f"Request ID: {request_id} deferred to NURSE.")
    except Exception as e:
        print(f"ERROR deferring request {request_id}: {e}")

@socketio.on("complete_request")
def handle_complete_request(data):
    """
    Expected data:
      - request_id (required)
      - nurse_name (optional)
      - room_number (optional; if missing, we'll look it up)
      - role (optional; 'nurse' | 'cna')
    """
    request_id = data.get("request_id")
    if not request_id:
        return  # nothing to do

    now_utc = datetime.now(timezone.utc)
    try:
        # 1) Mark complete in DB
        with engine.connect() as connection:
            trans = connection.begin()
            try:
                connection.execute(
                    text("""
                        UPDATE requests
                        SET completion_timestamp = :now
                        WHERE request_id = :request_id
                           OR CAST(id AS VARCHAR) = :request_id;
                    """),
                    {"now": now_utc, "request_id": request_id},
                )
                trans.commit()
                log_to_audit_trail(
                    "Request Completed",
                    f"Request ID: {request_id} marked as complete."
                )
            except Exception:
                trans.rollback()
                raise

        # 2) Remove from dashboards
        socketio.emit("remove_request", {"id": request_id})

        # 3) Notify patient only when we have a valid room
        room_number = data.get("room_number") or _get_room_for_request(request_id)
        role = (data.get("role") or "nurse").lower().strip()
        if role not in ("nurse", "cna"):
            role = "nurse"

        if room_number and _valid_room(str(room_number)):
            emit_patient_event(
                "request:done",
                room_number,
                {
                    "request_id": request_id,
                    "status": "completed",
                    "nurse": data.get("nurse_name"),
                    "role": role,
                    "ts": now_utc.isoformat(),
                },
            )
        # If room is missing/invalid, we just skip the patient emit.
    except Exception as e:
        print(f"ERROR updating completion timestamp: {e}")


# --- App Startup ---
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)












































































































