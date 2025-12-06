import spacy
from spacy.matcher import Matcher
from enum import Enum
from dataclasses import dataclass
from typing import List

try:
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
except OSError:
    nlp = spacy.blank("en")

class Routing(str, Enum):
    CNA = "CNA"
    NURSE = "NURSE"

class Tier(str, Enum):
    ROUTINE = "ROUTINE"
    EMERGENT = "EMERGENT"

@dataclass
class TriageResult:
    routing: Routing
    tier: Tier
    detected_patterns: List[str]

class TriageEngine:
    def __init__(self):
        self.matcher = Matcher(nlp.vocab)
        self._register_patterns()

    def _register_patterns(self):
        # --- A. EMERGENCIES (The "Iron Dome") ---
        
        # 1. HEART & CHEST
        self.matcher.add("EMERGENT_CHEST", [
            [{"LOWER": "chest"}, {"OP": "*"}, {"LEMMA": {"in": ["pain", "hurt", "pressure", "tight", "heavy", "crush", "discomfort"]}}],
            [{"LOWER": "heart"}, {"OP": "*"}, {"LEMMA": {"in": ["race", "pound", "palpitation", "skip", "stop"]}}],
            [{"LOWER": "heart"}, {"LOWER": "attack"}],
        ])

        # 2. BREATHING
        self.matcher.add("EMERGENT_BREATH", [
            [{"LEMMA": "short"}, {"LOWER": "of"}, {"LEMMA": "breath"}],
            [{"LEMMA": {"in": ["hard", "trouble", "struggle", "difficult"]}}, {"OP": "*"}, {"LEMMA": {"in": ["breath", "breathe"]}}],
            [{"LEMMA": {"in": ["gasp", "suffocate", "choke", "wheeze"]}}]
        ])

        # 3. HEAVY BLEEDING
        self.matcher.add("EMERGENT_BLEED", [
            [{"LEMMA": {"in": ["gush", "pour"]}}], 
            [{"LOWER": "running"}, {"LOWER": "down"}, {"LOWER": "leg"}],
            [{"LEMMA": "soak"}, {"OP": "*"}, {"LEMMA": "pad"}], 
            [{"LEMMA": "clot"}, {"OP": "*"}, {"LEMMA": {"in": ["golf", "baseball", "fist", "huge", "large"]}}]
        ])

        # 4. NEURO / STROKE / VISION / DIZZY / SEIZURE
        self.matcher.add("EMERGENT_NEURO", [
            [{"LEMMA": "slur"}], 
            [{"LEMMA": "droop"}], 
            [{"LEMMA": {"in": ["seizure", "seize", "seizing", "convulse", "twitch"]}}], # Added "SEIZE/SEIZING"
            [{"LEMMA": "faint"}],
            [{"LEMMA": {"in": ["dizzy", "lightheaded", "woozy"]}}], 
            
            # Vision
            [{"LEMMA": "vision"}, {"OP": "*"}, {"LEMMA": {"in": ["blur", "black", "double", "spot", "star", "flash"]}}],
            [{"LEMMA": "see"}, {"OP": "*"}, {"LEMMA": {"in": ["spot", "star", "flash", "sparkle"]}}],
            [{"LEMMA": "see"}, {"OP": "*"}, {"LOWER": "double"}]
        ])

        # 5. BABY SAFETY
        self.matcher.add("EMERGENT_BABY", [
            # Color (Added GREY)
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": {"in": ["blue", "purple", "gray", "grey", "limp", "floppy", "pale"]}}],
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": "unresponsive"}],
            # Baby won't wake (Smart Pattern)
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LEMMA": "wake"}], # Catches "won't wake", "not waking", "wont wake"
        ])

        # --- B. LOGISTICS (The "Firewall") ---
        
        self.matcher.add("LOGISTICS_ITEM", [
            [{"LEMMA": {"in": ["water", "ice", "snack", "cracker", "juice"]}}],
            [{"LEMMA": {"in": ["blanket", "pillow", "sheet", "gown", "sock", "slipper", "towel"]}}],
            [{"LEMMA": {"in": ["diaper", "wipe", "swaddle", "formula", "pacifier"]}}],
            [{"LOWER": {"in": ["tv", "remote", "charger", "phone", "wifi"]}}],
        ])

        self.matcher.add("LOGISTICS_ACT", [
            [{"LEMMA": "bathroom"}], 
            [{"LEMMA": "toilet"}],
            [{"LEMMA": "commode"}],
            [{"LEMMA": "shower"}],
            [{"LEMMA": "walk"}],
            [{"LEMMA": "help"}, {"LOWER": "up"}]
        ])
        
        # --- C. CLINICAL SYMPTOMS (Routine Nurse) ---
        self.matcher.add("CLINICAL_SYMPTOM", [
            [{"LEMMA": {"in": ["pain", "hurt", "ache", "sore", "cramp", "scar"]}}],
            [{"LEMMA": "medication"}],
            [{"LEMMA": "ibuprofen"}],
            [{"LEMMA": "tylenol"}],
            [{"LEMMA": "motrin"}],
            [{"LEMMA": "incision"}],
            [{"LEMMA": "stitch"}],
        ])

    def classify(self, text: str) -> TriageResult:
        t = (text or "").lower().strip()
        t = t.replace("’", "'") 
        
        # ------------------------------------------------------------
        # SAFETY OVERRIDE: "Dumb" String Matches (Bypasses AI)
        # ------------------------------------------------------------
        force_emergent_phrases = [
            # Breathing
            "cant breathe", "can't breathe", "cannot breathe", "can not breathe",
            "cant breath", "can't breath", "cannot breath", "can not breath",
            # Baby Drop
            "dropped my baby", "dropped the baby", "baby fell", "baby dropped",
            # Baby Wake/Lethargy (FIXED HERE)
            "wont wake", "won't wake", "not waking", "unresponsive",
            "baby wont wake", "baby won't wake"
        ]
        
        if any(phrase in t for phrase in force_emergent_phrases):
             print(f"DEBUG_OVERRIDE: Found '{t}' -> FORCE EMERGENT")
             return TriageResult(Routing.NURSE, Tier.EMERGENT, ["SAFETY_OVERRIDE"])
        
        # ------------------------------------------------------------
        # END OVERRIDE - Proceed to Smart NLP
        # ------------------------------------------------------------

        doc = nlp(t) 
        matches = self.matcher(doc)
        detected_labels = set([nlp.vocab.strings[match_id] for match_id, start, end in matches])
        
        # 1. EMERGENCIES
        emergent_flags = [l for l in detected_labels if l.startswith("EMERGENT")]
        if emergent_flags:
            return TriageResult(Routing.NURSE, Tier.EMERGENT, list(detected_labels))

        # 2. LOGISTICS
        logistics_flags = [l for l in detected_labels if l.startswith("LOGISTICS")]
        clinical_flags = [l for l in detected_labels if l.startswith("CLINICAL")]
        
        if logistics_flags and not clinical_flags:
            return TriageResult(Routing.CNA, Tier.ROUTINE, list(detected_labels))

        # 3. DEFAULT
        return TriageResult(Routing.NURSE, Tier.ROUTINE, list(detected_labels))
