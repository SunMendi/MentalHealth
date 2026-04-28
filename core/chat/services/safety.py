import re

CRISIS_KEYWORDS = [
    r"suicide", r"kill myself", r"want to die", r"end my life", 
    r"self-harm", r"hurt myself", r"cutting", r"overdose"
]

def check_for_crisis(content):
    """
    Returns True if any high-risk keywords are found.
    """
    for pattern in CRISIS_KEYWORDS:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False

def get_emergency_response():
    return {
        "empathetic_response": "I'm very concerned about what you're sharing. You don't have to go through this alone. Please reach out to a crisis hotline or emergency services immediately.",
        "detected_category": "Crisis",
        "confidence_score": 1.0,
        "suggested_buttons": ["Emergency Numbers", "Call a Friend"],
        "is_crisis": True
    }
