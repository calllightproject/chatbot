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
        
        # Breathing Logic
        self.matcher.add("EMERGENT_BREATH", [
            # 1. The Contraction Split: "ca" + "n't" + "breathe" (Fixes "I can't breathe")
            [{"LOWER": "ca"}, {"LOWER": "n't"}, {"LEMMA": "breathe"}],
            
            # 2. The Typos: "cant breathe" (No apostrophe)
            [{"LOWER": "cant"}, {"LEMMA": "breathe"}],
            
            # 3. The Full Words: "cannot breathe" or "can not breathe"
            [{"LOWER": "cannot"}, {"LEMMA": "breathe"}],
            [{"LOWER": "can"}, {"LOWER": "not"}, {"LEMMA": "breathe"}],

            # 4. Other distress
            [{"LEMMA": "short"}, {"LOWER": "of"}, {"LEMMA": "breath"}],
            [{"LEMMA": "gasp"}],
            [{"LEMMA": "suffocate"}],
            [{"LEMMA": "choke"}],
        ])

        # Heavy Bleeding
        self.matcher.add("EMERGENT_BLEED", [
            [{"LEMMA": "gush"}], 
            [{"LOWER": "running"}, {"LOWER": "down"}, {"LOWER": "leg"}],
            [{"LEMMA": "soak"}, {"OP": "*"}, {"LEMMA": "pad"}], 
            [{"LEMMA": "clot"}, {"OP": "*"}, {"LEMMA": {"in": ["golf", "baseball", "fist", "huge", "large"]}}]
        ])

        # Neuro/Stroke
        self.matcher.add("EMERGENT_NEURO", [
            [{"LEMMA": "slur"}], 
            [{"LEMMA": "droop"}], 
            [{"LEMMA": "seizure"}], 
            [{"LEMMA": "vision"}, {"OP": "*"}, {"LEMMA": {"in": ["blur", "black", "double", "spot"]}}]
        ])

        # Baby Emergencies (Blue/Limp)
        self.matcher.add("EMERGENT_BABY", [
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": {"in": ["blue", "purple", "gray", "limp", "floppy"]}}],
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": "wo"}, {"LOWER": "n't"}, {"LEMMA": "wake"}] # "wo" + "n't" split
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
        doc = nlp(text)
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
