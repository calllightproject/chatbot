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
        # A. EMERGENCIES (The "Iron Dome")
        # =========================================================
        
        # 1. HEART & CHEST (Bidirectional)
        self.matcher.add("EMERGENT_CHEST", [
            # "Chest" -> "Pain"
            [{"LOWER": "chest"}, {"OP": "*"}, {"LEMMA": {"in": ["pain", "hurt", "pressure", "tight", "heavy", "crush", "discomfort"]}}],
            # "Pain" -> "Chest"
            [{"LEMMA": {"in": ["pain", "hurt", "pressure", "tight", "heavy", "crush"]}}, {"OP": "*"}, {"LOWER": "chest"}],
            # Heart specific
            [{"LOWER": "heart"}, {"OP": "*"}, {"LEMMA": {"in": ["race", "pound", "palpitation", "skip", "stop", "attack"]}}],
        ])

        # 2. BREATHING
        self.matcher.add("EMERGENT_BREATH", [
            [{"LEMMA": "short"}, {"LOWER": "of"}, {"LEMMA": "breath"}],
            [{"LEMMA": {"in": ["hard", "trouble", "struggle", "difficult"]}}, {"OP": "*"}, {"LEMMA": {"in": ["breath", "breathe"]}}],
            [{"LEMMA": {"in": ["breath", "breathe"]}}, {"OP": "*"}, {"LEMMA": {"in": ["hard", "trouble", "struggle", "difficult"]}}],
            [{"LEMMA": {"in": ["gasp", "suffocate", "choke", "wheeze"]}}]
        ])

        # 3. HEAVY BLEEDING
        self.matcher.add("EMERGENT_BLEED", [
            [{"LEMMA": {"in": ["gush", "pour", "vomit", "throw"]}}, {"OP": "*"}, {"LEMMA": "blood"}], 
            [{"LOWER": "running"}, {"LOWER": "down"}, {"LOWER": "leg"}],
            [{"LEMMA": "soak"}, {"OP": "*"}, {"LEMMA": "pad"}], 
            # Clot sizes
            [{"LEMMA": "clot"}, {"OP": "*"}, {"LEMMA": {"in": ["golf", "baseball", "fist", "huge", "large", "giant", "massive"]}}],
            [{"LEMMA": {"in": ["huge", "large", "giant", "massive"]}}, {"OP": "*"}, {"LEMMA": "clot"}] 
        ])

        # 4. NEURO / STROKE / VISION / DIZZY
        self.matcher.add("EMERGENT_NEURO", [
            # General Neuro
            [{"LEMMA": "slur"}], 
            [{"LEMMA": {"in": ["seizure", "seize", "seizing", "convulse", "twitch"]}}],
            [{"LEMMA": "faint"}],
            [{"LOWER": "pass"}, {"LOWER": "out"}], 
            [{"LEMMA": {"in": ["dizzy", "lightheaded", "woozy"]}}], 
            
            # Face/Smile/Speech
            [{"LEMMA": {"in": ["face", "smile", "mouth"]}}, {"OP": "*"}, {"LEMMA": {"in": ["droop", "sag", "crook", "uneven", "numb"]}}],
            [{"LEMMA": "word"}, {"OP": "*"}, {"LEMMA": {"in": ["slur", "garble", "wrong", "stuck", "weird"]}}],
            [{"LEMMA": "word"}, {"OP": "*"}, {"LOWER": "wo"}, {"LOWER": "n't"}, {"LEMMA": "come"}],
            [{"LEMMA": "speech"}, {"OP": "*"}, {"LEMMA": {"in": ["slur", "weird", "strange", "garble", "funny"]}}], # Added "FUNNY"
            [{"LEMMA": "can"}, {"LOWER": "not"}, {"LEMMA": "speak"}],

            # Vision (Bidirectional)
            [{"LEMMA": "vision"}, {"OP": "*"}, {"LEMMA": {"in": ["blur", "blurry", "blurred", "black", "double", "spot", "star", "flash", "fuzzy"]}}],
            [{"LEMMA": {"in": ["blur", "blurry", "blurred", "black", "double", "fuzzy"]}}, {"OP": "*"}, {"LEMMA": {"in": ["vision", "see", "look", "everything"]}}], 
            [{"LEMMA": {"in": ["blur", "blurry", "blurred", "fuzzy"]}}], 
            
            # "Seeing" things
            [{"LEMMA": "see"}, {"OP": "*"}, {"LEMMA": {"in": ["spot", "star", "flash", "sparkle", "double"]}}],
            
            # Headache Red Flags
            [{"LEMMA": "headache"}, {"OP": "*"}, {"LEMMA": {"in": ["worst", "severe", "explode", "pounding", "killer", "blind"]}}],
            [{"LEMMA": {"in": ["worst", "severe", "explode", "pounding", "killer", "blind"]}}, {"OP": "*"}, {"LEMMA": {"in": ["headache", "head", "migraine"]}}],
            [{"LEMMA": "headache"}, {"OP": "*"}, {"LOWER": "wo"}, {"LOWER": "n't"}, {"LEMMA": "go"}], 
        ])

        # 5. INFECTION / SEPSIS / DEHISCENCE
        self.matcher.add("EMERGENT_INFECTION", [
            [{"LEMMA": {"in": ["pus", "ooze", "drain", "leak"]}}], 
            # Dehiscence
            [{"LEMMA": {"in": ["stitch", "incision", "staple", "wound"]}}, {"OP": "*"}, {"LEMMA": {"in": ["open", "pop", "split", "tear", "leak", "gape", "gaping"]}}], 
            [{"LEMMA": {"in": ["open", "pop", "split", "tear", "leak", "gape", "gaping"]}}, {"OP": "*"}, {"LEMMA": {"in": ["stitch", "incision", "staple", "wound"]}}],
        ])

        # 6. PAIN LOCATIONS (Bidirectional)
        self.matcher.add("EMERGENT_PAIN_LOC", [
            # Calf/Leg DVT
            [{"LEMMA": {"in": ["calf", "leg"]}}, {"OP": "*"}, {"LEMMA": {"in": ["hot", "red", "swollen", "swell", "pain", "hurts"]}}],
            [{"LEMMA": {"in": ["hot", "red", "swollen", "swell", "pain", "hurts"]}}, {"OP": "*"}, {"LEMMA": {"in": ["calf", "leg"]}}],
            
            # Preeclampsia (Upper Belly/Ribs)
            [{"LEMMA": {"in": ["pain", "hurt", "severe"]}}, {"OP": "*"}, {"LEMMA": {"in": ["rib", "ribs"]}}],
            [{"LEMMA": {"in": ["upper", "top", "high"]}}, {"OP": "*"}, {"LEMMA": {"in": ["belly", "stomach", "abdomen"]}}, {"OP": "*"}, {"LEMMA": {"in": ["pain", "hurt"]}}], 
            [{"LEMMA": {"in": ["pain", "hurt"]}}, {"OP": "*"}, {"LEMMA": {"in": ["upper", "top", "high"]}}, {"OP": "*"}, {"LEMMA": {"in": ["belly", "stomach", "abdomen"]}}]
        ])

        # 7. BABY SAFETY (Expanded)
        self.matcher.add("EMERGENT_BABY", [
            # Color
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LOWER": {"in": ["blue", "purple", "gray", "grey", "limp", "floppy", "pale", "stiff", "sweat", "sweating", "clammy"]}}],
            # Lethargy/Seizures
            [{"LEMMA": "baby"}, {"OP": "*"}, {"LEMMA": {"in": ["lethargic", "unresponsive", "listless", "shake", "shaking", "twitch", "seize", "impossible"]}}],
            [{"LEMMA": {"in": ["hard", "impossible"]}}, {"OP": "*"}, {"LEMMA": "wake"}, {"OP": "*"}, {"LEMMA": "baby"}],
        ])

        # =========================================================
        # B. LOGISTICS (The "Firewall")
        # =========================================================
        self.matcher.add("LOGISTICS_ITEM", [
            [{"LEMMA": {"in": ["water", "ice", "snack", "cracker", "juice"]}}],
            [{"LEMMA": {"in": ["blanket", "pillow", "sheet", "gown", "sock", "slipper", "towel"]}}],
            [{"LEMMA": {"in": ["diaper", "wipe", "swaddle", "formula", "pacifier"]}}],
            # Expanded Supply List
            [{"LOWER": {"in": ["mesh", "underwear", "panties", "chux", "pad", "pads", "liner", "liners"]}}],
            [{"LOWER": {"in": ["peri", "bottle"]}}],
            [{"LOWER": {"in": ["tv", "remote", "charger", "phone", "wifi", "bed"]}}],
            # REMOVED: pump, flange, part (Now defaults to Nurse)
        ])

        self.matcher.add("LOGISTICS_ACT", [
            [{"LEMMA": "bathroom"}], 
            [{"LEMMA": "toilet"}],
            [{"LEMMA": "commode"}],
            [{"LEMMA": "shower"}],
            [{"LEMMA": "walk"}],
            [{"LEMMA": "help"}, {"LOWER": "up"}],
            # Room Environment
            [{"LEMMA": {"in": ["room", "temperature", "thermostat"]}}],
            [{"LOWER": {"in": ["freezing", "cold", "hot", "burning", "boiling"]}}]
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
            # Smells (Routine Clinical)
            [{"LEMMA": "smell"}, {"OP": "*"}, {"LEMMA": {"in": ["rot", "dead", "foul", "meat", "bad", "weird"]}}], 
            [{"LEMMA": "foul"}, {"OP": "*"}, {"LEMMA": "smell"}],
        ])

    def _check_bp_danger(self, text: str) -> bool:
        """Regex for BP >= 160 systolic OR >= 110 diastolic."""
        systolic = re.findall(r'\b(1[6-9][0-9]|2[0-9]{2})\b', text)
        if systolic: return True
        diastolic = re.findall(r'\b(1[1-9][0-9])\b', text)
        if diastolic: return True
        return False

    def classify(self, text: str) -> TriageResult:
        t = (text or "").lower().strip()
        t = t.replace("’", "'") 
        
        # 1. SAFETY OVERRIDE: Dumb String Matches
        force_emergent_phrases = [
            "cant breathe", "can't breathe", "cannot breathe", "can not breathe",
            "cant breath", "can't breath", "cannot breath", "can not breath",
            "dropped my baby", "dropped the baby", "baby fell", "baby dropped", "rolled off",
            "wont wake", "won't wake", "not waking", "unresponsive", "hard to wake",
            "baby wont", "baby won't",
            "going to die", "gonna die", "dying"
        ]
        
        if any(phrase in t for phrase in force_emergent_phrases):
             print(f"DEBUG_OVERRIDE: Found '{t}' -> FORCE EMERGENT")
             return TriageResult(Routing.NURSE, Tier.EMERGENT, ["SAFETY_OVERRIDE"])

        # 2. BP CHECK
        if self._check_bp_danger(t):
             return TriageResult(Routing.NURSE, Tier.EMERGENT, ["DANGEROUS_BP"])

        # 3. SMART NLP PATTERNS
        doc = nlp(t) 
        matches = self.matcher(doc)
        detected_labels = set([nlp.vocab.strings[match_id] for match_id, start, end in matches])
        
        emergent_flags = [l for l in detected_labels if l.startswith("EMERGENT")]
        logistics_flags = [l for l in detected_labels if l.startswith("LOGISTICS")]
        clinical_flags = [l for l in detected_labels if l.startswith("CLINICAL")]

        # GAS PAIN DOWNGRADE
        if emergent_flags and "gas" in t:
            if all(f == "EMERGENT_PAIN_LOC" for f in emergent_flags):
                return TriageResult(Routing.NURSE, Tier.ROUTINE, ["DOWNGRADED_GAS_PAIN"])

        if emergent_flags:
            return TriageResult(Routing.NURSE, Tier.EMERGENT, list(detected_labels))

        if logistics_flags and not clinical_flags:
            return TriageResult(Routing.CNA, Tier.ROUTINE, list(detected_labels))

        return TriageResult(Routing.NURSE, Tier.ROUTINE, list(detected_labels))
