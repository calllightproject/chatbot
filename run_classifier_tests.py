# run_classifier_tests.py
#
# Usage:
#   python run_classifier_tests.py
#
# It imports classify_escalation_tier + route_note_intelligently from app.py
# and bulk-tests phrases, printing PASS/FAIL.

from app import classify_escalation_tier, route_note_intelligently

EMERGENT_TESTS = [
    # Neuro – speech / confusion / awareness
    "My speech suddenly got slurred and I can’t get the words out right",
    "I suddenly can’t understand the words people are saying to me",
    "I feel extremely confused and something is seriously wrong",
    "I keep blacking out for a second and then coming back confused",
    "I feel like my brain is shutting down and I can’t process anything anyone says",
    "I keep losing awareness for a few seconds at a time",
    "I feel like I’m drifting away and can’t stay awake or alert",
    "My words keep coming out wrong and I can’t say what I’m thinking",
    "I can hear people talking but I can’t respond or move my mouth the way I want",
    "I suddenly can’t get any words out even though I know what I want to say",

    # Neuro – focal weakness / face
    "My left side suddenly feels weak and heavy and I can barely move it",
    "My right arm dropped suddenly and I can’t control my hand",
    "My face suddenly feels numb and I can’t move my mouth normally",
    "My smile looks crooked and I can’t move one side of my face",
    "My legs collapsed underneath me and I couldn’t catch myself",

    # Neuro – jerking / shaking
    "My whole body suddenly started shaking and I couldn’t control any of it",
    "My hands are shaking violently and I can’t make them stop",
    "My body keeps jerking on its own and I can’t stop it",
    "My whole body started jerking and I couldn’t control any part of it",
    "I can’t stop shaking and my body won’t respond when I try to move",

    # Baby neuro red flags
    "My baby’s eyes keep rolling back and they won’t respond when I talk or touch them",
    "My baby won’t look at me at all and their eyes seem to drift upward",
    "My baby is staring straight ahead and won’t react when I touch them",
    "My baby suddenly became very stiff and their eyes won’t focus",
    "My baby feels floppy and isn’t responding when I try to wake them",

    # HTN / preeclampsia-ish neuro overlap
    "I’m seeing little flashing lights and my eyes feel strained and painful",
    "I have a really bad headache that won’t go away even after meds",
    "My headache is getting worse really fast and I feel out of it",
    "My whole body feels shaky and sick and I feel this sense that something terrible is about to happen",
    "I feel like I’m about to pass out and my head feels wrong",
]

def run_tests():
    print("=== EMERGENT NEURO/HTN TESTS ===")
    failures = 0
    for phrase in EMERGENT_TESTS:
        tier = classify_escalation_tier(phrase)
        role = route_note_intelligently(phrase)
        ok = (tier == "emergent" and role == "nurse")
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] tier={tier:<8} role={role:<5} :: {phrase}")
        if not ok:
            failures += 1

    print("\nSummary:")
    print(f"  Total tests: {len(EMERGENT_TESTS)}")
    print(f"  Failures   : {failures}")
    if failures == 0:
        print("  ✅ All emergent tests routed as nurse/emergent.")
    else:
        print("  ❌ Some phrases did NOT route as nurse/emergent. See FAIL lines above.")

if __name__ == "__main__":
    run_tests()
