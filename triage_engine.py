import spacy
from spacy.matcher import Matcher
from enum import Enum
from dataclasses import dataclass
from typing import List

# =========================================================
# 1. SETUP & CONFIGURATION
# =========================================================

try:
    # Load the small English model
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
except OSError:
    # Fallback if model isn't found locally yet
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

# =========================================================
# 2. THE TRIAGE ENGINE
# =========================================================

class TriageEngine:
    def __init__(self):
        self.matcher = Matcher(nlp.vocab)
        self._register_patterns()

    def _register_patterns(self):
        """
        Define rules using Token Patterns.
        """
        
        # --- A. EMERGENCIES (The "Iron Dome") ---
        
        # 1. HEART & CHEST (The Missing Piece)
        self.matcher.add("EMERGENT_CHEST", [
            [{"LOWER": "chest"}, {"LEMMA": {"in": ["pain", "hurt", "pressure", "tight", "heavy", "crush"]}}],
            [{"LOWER": "heart"}, {"LEMMA": {"in": ["race", "pound", "palpitation", "skip", "stop"]}}],
            [{"LOWER": "heart"}, {"LOWER": "attack"}],
        ])

        # 2. BREATHING (Smart Patterns)
        self.matcher.add("EMERGENT_BREATH", [
            # "Short of breath"
            [{"LEMMA": "short"}, {"LOWER": "of"}, {"LEMMA": "breath"}],
            # "Hard to breathe"
            [{"LEMMA": {"in": ["hard", "trouble", "struggle", "difficult"]}}, {"OP": "*"}, {"LEMMA": {"in": ["breath", "breathe"]}}],
            # Keywords
            [{"LEMMA": {"in": ["gasp", "suffocate", "choke", "wheeze"]}}]
        ])

        # 3. HEAVY BLEEDING
        self.matcher.add("EMERGENT_BLEED", [
            [{"LEMMA": "gush"}], 
            [{"LOWER": "running"}, {"LOWER": "down"}, {"LOWER": "leg"}],
            [{"LEMMA": "soak"}, {"OP": "*"}, {"LEMMA": "pad"}], 
            [{"LEMMA": "clot"}, {"OP": "*"}, {"LEMMA": {"in": ["golf", "baseball", "fist", "huge", "large"]}}]
        ])

        # 4. NEURO / STROKE / SEIZURE
        self.matcher.add("EMERGENT_NEURO", [
            [{"LEMMA": "slur"}], 
            [{"LEMMA": "droop"}], 
            [{"LEMMA": "seizure"}], 
            [{"LEMMA": "vision"}, {"OP": "*"}, {"LEMMA": {"in": ["blur", "black", "double", "spot", "star"]}}]
        ])

        # 5. BABY SAFETY
        self.matcher.add("EMERGENT_BABY", [
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": {"in": ["blue", "purple", "gray", "limp", "floppy", "pale"]}}],
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": "unresponsive"}]
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
            [{"LEMMA": {"in": ["pain", "hurt", "ache", "sore", "cramp"]}}],
            [{"LEMMA": "medication"}],
            [{"LEMMA": "tylenol"}],
            [{"LEMMA": "motrin"}],
            [{"LEMMA": "incision"}],
            [{"LEMMA": "stitch"}],
        ])

    def classify(self, text: str) -> TriageResult:
        # 1. Clean the text
        t = (text or "").lower().strip()
        t = t.replace("’", "'") # Normalize curly quotes
        
        # ------------------------------------------------------------
        # SAFETY OVERRIDE: "Dumb" String Matches (Bypasses AI)
        # ------------------------------------------------------------
        # If any of these strings exist, we trigger EMERGENT immediately.
        # This fixes "cant breathe", "can not breathe", "dropped baby", etc.
        
        force_emergent_phrases = [
            "cant breathe", "can't breathe", "cannot breathe", "can not breathe",
            "cant breath", "can't breath", "cannot breath", "can not breath",
            "dropped my baby", "dropped the baby", "baby fell", "baby dropped"
        ]
        
        if any(phrase in t for phrase in force_emergent_phrases):
             # Log this so you see it in Render logs
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
