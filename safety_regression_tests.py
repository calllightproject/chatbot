"""
Tiny safety regression test runner.

Goal:
- Make sure our routing + escalation never silently stops treating red flags
  as emergent/nurse.
- Every phrase in TEST_GROUPS should:
    - classify_escalation_tier(...) == "emergent"
    - route_note_intelligently(...) == "nurse"
"""

from app import classify_escalation_tier, route_note_intelligently


# --- TEST PHRASE GROUPS -----------------------------------------------------

TEST_GROUPS = {
    # Adult neuro red flags
    "neuro_adult": [
        "My left side suddenly feels weak and heavy and I can barely move it",
        "My smile looks crooked and I can't move one side of my face",
        "I can't stop shaking and my body won't respond when I try to move",
        "My speech suddenly got slurred and I can't get the words out right",
        "I keep losing awareness for a few seconds at a time",
        "I feel like I'm drifting away and can't stay awake or alert",
        "My head feels like it's exploding and I'm getting very confused",
        "I suddenly can't understand the words people are saying to me",
        "I can hear people talking but I can't respond or move my mouth the way I want",
        "My words keep coming out wrong and I can't say what I'm thinking",
    ],

    # Baby neuro red flags
    "neuro_baby": [
        "My baby suddenly became very stiff and their eyes won't focus",
        "My baby is staring straight ahead and won't react when I touch them",
        "My baby's eyes keep rolling back and they won't respond when I talk or touch them",
        "My baby won't look at me at all and their eyes seem to drift upward",
        "My baby feels very floppy and won't react when I pick them up",
    ],

    # Heart / breathing / color-change red flags
    "heart_breath_color": [
        "I can't breathe and my chest feels tight and heavy",
        "I have a crushing pressure in the center of my chest and it's hard to breathe",
        "My chest suddenly started hurting and I feel like I can't get enough air",
        "My baby looks blue around the lips and is breathing weird",
        "My lips and fingertips suddenly look blue and I feel short of breath",
    ],

    # PPH / heavy bleeding red flags
    "pph_bleeding": [
        "Bright red blood is running down my legs and soaking through pads",
        "I am bleeding a lot and soaking through a pad in less than an hour",
        "I passed a blood clot the size of a golf ball",
        "I'm bleeding heavily and feel dizzy and like I'm going to faint",
    ],

    # HTN / preeclampsia red flags
    "htn_preeclampsia": [
        "I have a really bad headache that won't go away even after medicine",
        "I'm seeing spots and sparkles and my head feels wrong",
        "I have sharp pain under my right ribs when I breathe",
        "My blood pressure was very high this morning and I feel really off",
        "I suddenly feel extremely confused and disoriented and something feels really wrong",
    ],
}


# --- TEST RUNNER -------------------------------------------------------------

def run_emergent_tests() -> None:
    total = 0
    failures = []

    for group_name, phrases in TEST_GROUPS.items():
        print(f"\n=== Testing group: {group_name} ===")
        for phrase in phrases:
            total += 1
            tier = classify_escalation_tier(phrase)
            role = route_note_intelligently(phrase)

            tier_ok = (tier == "emergent")
            role_ok = (role == "nurse")

            if tier_ok and role_ok:
                print(f"[OK]   tier={tier:8s} role={role:5s} :: {phrase}")
            else:
                print(f"[FAIL] tier={tier:8s} role={role:5s} :: {phrase}")
                failures.append((group_name, phrase, tier, role))

    print("\n" + "-" * 70)
    print(f"Total phrases tested: {total}")
    print(f"Total failures:       {len(failures)}")

    if failures:
        print("\nFailures detail:")
        for group_name, phrase, tier, role in failures:
            print(f"  group={group_name:16s} tier={tier:8s} role={role:5s} :: {phrase}")
    else:
        print("\n✅ ALL TESTS PASSED (for these phrases).")


if __name__ == "__main__":
    run_emergent_tests()
