import spacy
from spacy.matcher import Matcher
from enum import Enum
from dataclasses import dataclass
from typing import List

# =========================================================
# 1. SETUP & CONFIGURATION
# =========================================================

# Load the small English model we added to requirements.txt
try:
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
except OSError:
    # Fallback if model isn't found locally yet (prevents crash on first run)
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
        LEMMA handles word variations (run, running, runs).
        LOWER handles case (Bleeding, bleeding).
        """
        
        # --- A. EMERGENCIES (The "Iron Dome") ---
        
        # Breathing: "cant breathe", "short of breath", "gasping"
        self.matcher.add("EMERGENT_BREATH", [
            [{"LOWER": {"in": ["cant", "can't", "cannot"]}}, {"LEMMA": "breathe"}],
            [{"LEMMA": "short"}, {"LOWER": "of"}, {"LEMMA": "breath"}],
            [{"LEMMA": "gasp"}],
            [{"LEMMA": "suffocate"}],
        ])

        # Heavy Bleeding: "gushing", "soaked pad", "clots"
        self.matcher.add("EMERGENT_BLEED", [
            [{"LEMMA": "gush"}], 
            [{"LOWER": "running"}, {"LOWER": "down"}, {"LOWER": "leg"}],
            [{"LEMMA": "soak"}, {"OP": "*"}, {"LEMMA": "pad"}], 
            [{"LEMMA": "clot"}, {"OP": "*"}, {"LEMMA": {"in": ["golf", "baseball", "fist", "huge", "large"]}}]
        ])

        # Neuro/Stroke: "slurred speech", "drooping", "seizure"
        self.matcher.add("EMERGENT_NEURO", [
            [{"LEMMA": "slur"}], 
            [{"LEMMA": "droop"}], 
            [{"LEMMA": "seizure"}], 
            [{"LEMMA": "vision"}, {"OP": "*"}, {"LEMMA": {"in": ["blur", "black", "double", "spot"]}}]
        ])

        # --- B. LOGISTICS (The "Firewall") ---
        
        # Supplies: "water", "blanket", "charger", "remote"
        self.matcher.add("LOGISTICS_ITEM", [
            [{"LEMMA": {"in": ["water", "ice", "snack", "cracker", "juice"]}}],
            [{"LEMMA": {"in": ["blanket", "pillow", "sheet", "gown", "sock", "slipper", "towel"]}}],
            [{"LEMMA": {"in": ["diaper", "wipe", "swaddle", "formula", "pacifier"]}}],
            [{"LOWER": {"in": ["tv", "remote", "charger", "phone", "wifi"]}}],
        ])

        # Actions: "bathroom", "shower", "walk"
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
        doc = nlp(text)
        matches = self.matcher(doc)
        
        # Get list of matched labels (e.g., "LOGISTICS_ITEM", "EMERGENT_BREATH")
        detected_labels = set([nlp.vocab.strings[match_id] for match_id, start, end in matches])
        
        # 1. CHECK EMERGENCIES FIRST
        emergent_flags = [l for l in detected_labels if l.startswith("EMERGENT")]
        if emergent_flags:
            return TriageResult(Routing.NURSE, Tier.EMERGENT, list(detected_labels))

        # 2. CHECK LOGISTICS
        logistics_flags = [l for l in detected_labels if l.startswith("LOGISTICS")]
        clinical_flags = [l for l in detected_labels if l.startswith("CLINICAL")]
        
        # If it is Logistics AND NOT Clinical -> CNA
        if logistics_flags and not clinical_flags:
            return TriageResult(Routing.CNA, Tier.ROUTINE, list(detected_labels))

        # 3. DEFAULT TO NURSE
        return TriageResult(Routing.NURSE, Tier.ROUTINE, list(detected_labels))
