import spacy
from spacy.matcher import Matcher
from enum import Enum
from dataclasses import dataclass
from typing import List

# =========================================================
# 1. SETUP & CONFIGURATION
# =========================================================

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
        
        # 1. BREATHING (BRUTE FORCE PATTERNS)
        # We use LOWER checks to catch exact spellings/typos, bypassing grammar logic.
        # ------------------------------------------------------
        self.matcher.add("EMERGENT_BREATH", [
            # "I can't breathe" (Standard English splits into "ca" + "n't")
            [{"LOWER": "ca"}, {"LOWER": "n't"}, {"LOWER": {"in": ["breathe", "breath", "breathing"]}}],
            
            # "cant breathe" (Typo: one word)
            [{"LOWER": "cant"}, {"LOWER": {"in": ["breathe", "breath", "breathing"]}}],
            
            # "cannot breathe"
            [{"LOWER": "cannot"}, {"LOWER": {"in": ["breathe", "breath", "breathing"]}}],
            
            # "can not breathe" (Three words)
            [{"LOWER": "can"}, {"LOWER": "not"}, {"LOWER": {"in": ["breathe", "breath", "breathing"]}}],

            # "Hard to breathe" / "Short of breath"
            [{"LEMMA": {"in": ["hard", "trouble", "struggle", "difficult"]}}, {"OP": "*"}, {"LEMMA": {"in": ["breath", "breathe"]}}],
            [{"LEMMA": "short"}, {"LOWER": "of"}, {"LEMMA": "breath"}],
            
            # "No air"
            [{"LOWER": "no"}, {"LOWER": "air"}],
            
            # Keywords
            [{"LEMMA": "gasp"}],
            [{"LEMMA": "suffocate"}],
            [{"LEMMA": "choke"}],
        ])

        # 2. BABY SAFETY (Dropped, Blue, Limp)
        # ------------------------------------------------------
        self.matcher.add("EMERGENT_BABY", [
            # Dropped the baby (Trauma)
            [{"LEMMA": {"in": ["drop", "fall", "hit", "slip"]}}, {"OP": "*"}, {"LEMMA": "baby"}],
            [{"LEMMA": "baby"}, {"LEMMA": {"in": ["fall", "roll", "drop"]}}],

            # Color / Tone
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": {"in": ["blue", "purple", "gray", "limp", "floppy", "pale"]}}],
            
            # Responsiveness
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": "wo"}, {"LOWER": "n't"}, {"LEMMA": "wake"}], # wo + n't wake
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": "unresponsive"}],
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": "not"}, {"LEMMA": "breathing"}]
        ])

        # 3. HEAVY BLEEDING
        # ------------------------------------------------------
        self.matcher.add("EMERGENT_BLEED", [
            [{"LEMMA": "gush"}], 
            [{"LOWER": "running"}, {"LOWER": "down"}, {"LOWER": "leg"}],
            [{"LEMMA": "soak"}, {"OP": "*"}, {"LEMMA": "pad"}], 
            [{"LEMMA": "clot"}, {"OP": "*"}, {"LEMMA": {"in": ["golf", "baseball", "fist", "huge", "large"]}}]
        ])

        # 4. NEURO / STROKE / SEIZURE
        # ------------------------------------------------------
        self.matcher.add("EMERGENT_NEURO", [
            [{"LEMMA": "slur"}], 
            [{"LEMMA": "droop"}], 
            [{"LEMMA": "seizure"}], 
            [{"LEMMA": "vision"}, {"OP": "*"}, {"LEMMA": {"in": ["blur", "black", "double", "spot", "star"]}}]
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
        # Lowercase raw text to help spaCy with some capitalizations
        doc = nlp(text.lower()) 
        matches = self.matcher(doc)
        
        detected_labels = set([nlp.vocab.strings[match_id] for match_id, start, end in matches])
        
        # 1. CHECK EMERGENCIES FIRST
        emergent_flags = [l for l in detected_labels if l.startswith("EMERGENT")]
        if emergent_flags:
            return TriageResult(Routing.NURSE, Tier.EMERGENT, list(detected_labels))

        # 2. CHECK LOGISTICS
        logistics_flags = [l for l in detected_labels if l.startswith("LOGISTICS")]
        clinical_flags = [l for l in detected_labels if l.startswith("CLINICAL")]
        
        if logistics_flags and not clinical_flags:
            return TriageResult(Routing.CNA, Tier.ROUTINE, list(detected_labels))

        # 3. DEFAULT TO NURSE
        return TriageResult(Routing.NURSE, Tier.ROUTINE, list(detected_labels))
