import spacy
import re
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
        # =========================================================
        # A. EMERGENCY PATTERNS ("Iron Dome")
        # =========================================================
        
        # 1. HEART & CHEST (Bidirectional)
        # ---------------------------------------------------------
        self.matcher.add("EMERGENT_CHEST", [
            # "Chest" -> "Pain"
            [{"LOWER": "chest"}, {"OP": "*"}, {"LEMMA": {"in": ["pain", "hurt", "pressure", "tight", "heavy", "crush", "discomfort"]}}],
            # "Pain" -> "Chest" (Fixes "Pressure in my chest")
            [{"LEMMA": {"in": ["pain", "hurt", "pressure", "tight", "heavy", "crush"]}}, {"OP": "*"}, {"LOWER": "chest"}],
            # Heart specific
            [{"LOWER": "heart"}, {"OP": "*"}, {"LEMMA": {"in": ["race", "pound", "palpitation", "skip", "stop", "attack"]}}],
        ])

        # 2. BREATHING (Bidirectional)
        # ---------------------------------------------------------
        self.matcher.add("EMERGENT_BREATH", [
            # "Short of breath"
            [{"LEMMA": "short"}, {"LOWER": "of"}, {"LEMMA": "breath"}],
            # "Hard to breathe"
            [{"LEMMA": {"in": ["hard", "trouble", "struggle", "difficult"]}}, {"OP": "*"}, {"LEMMA": {"in": ["breath", "breathe"]}}],
            # "Breathing is hard"
            [{"LEMMA": {"in": ["breath", "breathe"]}}, {"OP": "*"}, {"LEMMA": {"in": ["hard", "trouble", "struggle", "difficult"]}}],
            # Keywords
            [{"LEMMA": {"in": ["gasp", "suffocate", "choke", "wheeze"]}}]
        ])

        # 3. HEAVY BLEEDING (Vomiting added)
        # ---------------------------------------------------------
        self.matcher.add("EMERGENT_BLEED", [
            [{"LEMMA": {"in": ["gush", "pour", "vomit", "throw"]}}, {"OP": "*"}, {"LEMMA": "blood"}], # "Vomiting blood"
            [{"LOWER": "running"}, {"LOWER": "down"}, {"LOWER": "leg"}],
            [{"LEMMA": "soak"}, {"OP": "*"}, {"LEMMA": "pad"}], 
            [{"LEMMA": "clot"}, {"OP": "*"}, {"LEMMA": {"in": ["golf", "baseball", "fist", "huge", "large"]}}]
        ])

        # 4. NEURO / STROKE / VISION / DIZZY
        # ---------------------------------------------------------
        self.matcher.add("EMERGENT_NEURO", [
            [{"LEMMA": "slur"}], 
            [{"LEMMA": "droop"}], 
            [{"LEMMA": {"in": ["seizure", "seize", "seizing", "convulse", "twitch"]}}],
            [{"LEMMA": "faint"}],
            [{"LEMMA": {"in": ["dizzy", "lightheaded", "woozy"]}}], 
            
            # Vision (Bidirectional)
            [{"LEMMA": "vision"}, {"OP": "*"}, {"LEMMA": {"in": ["blur", "black", "double", "spot", "star", "flash"]}}],
            [{"LEMMA": {"in": ["blur", "black", "double", "spot", "star", "flash"]}}, {"OP": "*"}, {"LEMMA": "vision"}], # "Blurry vision"
            
            # "Seeing" things
            [{"LEMMA": "see"}, {"OP": "*"}, {"LEMMA": {"in": ["spot", "star", "flash", "sparkle", "double"]}}],
            
            # Headache Red Flags
            [{"LEMMA": "headache"}, {"OP": "*"}, {"LEMMA": {"in": ["worst", "severe", "explode", "pounding"]}}],
            [{"LEMMA": "headache"}, {"OP": "*"}, {"LOWER": "wo"}, {"LOWER": "n't"}, {"LEMMA": "go"}], # "wont go away"
        ])

        # 5. INFECTION / SEPSIS / DEHISCENCE (New)
        # ---------------------------------------------------------
        self.matcher.add("EMERGENT_INFECTION", [
            [{"LEMMA": {"in": ["pus", "ooze", "drain"]}}], 
            [{"LEMMA": "foul"}, {"OP": "*"}, {"LEMMA": "smell"}],
            [{"LEMMA": "smell"}, {"OP": "*"}, {"LEMMA": {"in": ["rot", "dead", "foul", "meat"]}}],
            # Stitches open
            [{"LEMMA": {"in": ["stitch", "incision", "staple"]}}, {"OP": "*"}, {"LEMMA": {"in": ["open", "pop", "split", "tear"]}}], 
        ])

        # 6. DVT & PAIN LOCATIONS (New)
        # ---------------------------------------------------------
        self.matcher.add("EMERGENT_PAIN_LOC", [
            # Calf/Leg DVT
            [{"LEMMA": {"in": ["calf", "leg"]}}, {"OP": "*"}, {"LEMMA": {"in": ["hot", "red", "swollen", "swell", "pain"]}}],
            # RUQ / Ribs (Preeclampsia)
            [{"LEMMA": "pain"}, {"OP": "*"}, {"LEMMA": {"in": ["rib", "ribs"]}}],
            [{"LEMMA": "upper"}, {"LEMMA": "belly"}, {"OP": "*"}, {"LEMMA": "pain"}]
        ])

        # 7. BABY SAFETY (Expanded)
        # ---------------------------------------------------------
        self.matcher.add("EMERGENT_BABY", [
            # Color
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": {"in": ["blue", "purple", "gray", "grey", "limp", "floppy", "pale", "stiff"]}}],
            # Lethargy
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LEMMA": {"in": ["lethargic", "unresponsive", "listless"]}}],
            [{"LEMMA": "hard"}, {"OP": "*"}, {"LEMMA": "wake"}, {"OP": "*"}, {"LEMMA": "baby"}],
        ])

        # =========================================================
        # B. LOGISTICS (The "Firewall")
        # =========================================================
        self.matcher.add("LOGISTICS_ITEM", [
            [{"LEMMA": {"in": ["water", "ice", "snack", "cracker", "juice"]}}],
            [{"LEMMA": {"in": ["blanket", "pillow", "sheet", "gown", "sock", "slipper", "towel"]}}],
            [{"LEMMA": {"in": ["diaper", "wipe", "swaddle", "formula", "pacifier"]}}],
            [{"LOWER": {"in": ["tv", "remote", "charger", "phone", "wifi", "bed"]}}],
        ])

        self.matcher.add("LOGISTICS_ACT", [
            [{"LEMMA": "bathroom"}], 
            [{"LEMMA": "toilet"}],
            [{"LEMMA": "commode"}],
            [{"LEMMA": "shower"}],
            [{"LEMMA": "walk"}],
            [{"LEMMA": "help"}, {"LOWER": "up"}]
        ])
        
        # =========================================================
        # C. CLINICAL SYMPTOMS (Routine Nurse)
        # =========================================================
        self.matcher.add("CLINICAL_SYMPTOM", [
            [{"LEMMA": {"in": ["pain", "hurt", "ache", "sore", "cramp", "scar"]}}],
            [{"LEMMA": "medication"}],
            [{"LEMMA": "ibuprofen"}],
            [{"LEMMA": "tylenol"}],
            [{"LEMMA": "motrin"}],
            [{"LEMMA": "incision"}],
            [{"LEMMA": "stitch"}],
        ])

    def _check_bp_danger(self, text: str) -> bool:
        """
        Regex safety check for BP >= 160/110.
        Matches formats like "160/100", "180 over 110", "165".
        """
        # Look for systolic >= 160
        systolic = re.findall(r'\b(1[6-9][0-9]|2[0-9]{2})\b', text)
        if systolic: return True
        
        # Look for diastolic >= 110
        diastolic = re.findall(r'\b(1[1-9][0-9])\b', text)
        if diastolic: return True
        
        return False

    def classify(self, text: str) -> TriageResult:
        t = (text or "").lower().strip()
        t = t.replace("’", "'") 
        
        # 1. SAFETY OVERRIDE: Dumb String Matches
        # -----------------------------------------------------
        force_emergent_phrases = [
            # Breathing
            "cant breathe", "can't breathe", "cannot breathe", "can not breathe",
            "cant breath", "can't breath", "cannot breath", "can not breath",
            # Baby Trauma
            "dropped my baby", "dropped the baby", "baby fell", "baby dropped", "rolled off",
            # Baby Lethargy
            "wont wake", "won't wake", "not waking", "unresponsive", "hard to wake",
            "baby wont", "baby won't",
            # Impending Doom
            "going to die", "gonna die", "dying"
        ]
        
        if any(phrase in t for phrase in force_emergent_phrases):
             print(f"DEBUG_OVERRIDE: Found '{t}' -> FORCE EMERGENT")
             return TriageResult(Routing.NURSE, Tier.EMERGENT, ["SAFETY_OVERRIDE"])

        # 2. BP CHECK (Numeric)
        # -----------------------------------------------------
        if self._check_bp_danger(t):
             return TriageResult(Routing.NURSE, Tier.EMERGENT, ["DANGEROUS_BP"])

        # 3. SMART NLP PATTERNS
        # -----------------------------------------------------
        doc = nlp(t) 
        matches = self.matcher(doc)
        detected_labels = set([nlp.vocab.strings[match_id] for match_id, start, end in matches])
        
        # Check Emergencies
        emergent_flags = [l for l in detected_labels if l.startswith("EMERGENT")]
        if emergent_flags:
            return TriageResult(Routing.NURSE, Tier.EMERGENT, list(detected_labels))

        # Check Logistics
        logistics_flags = [l for l in detected_labels if l.startswith("LOGISTICS")]
        clinical_flags = [l for l in detected_labels if l.startswith("CLINICAL")]
        
        if logistics_flags and not clinical_flags:
            return TriageResult(Routing.CNA, Tier.ROUTINE, list(detected_labels))

        # Default
        return TriageResult(Routing.NURSE, Tier.ROUTINE, list(detected_labels))
