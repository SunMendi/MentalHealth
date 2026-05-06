import re
from typing import Dict, List, Optional


CURRENT_NEEDS = {
    "CALMING": "The user needs immediate calming or grounding.",
    "VALIDATION": "The user needs warmth, emotional acknowledgment, and to feel heard.",
    "ADVICE": "The user is explicitly asking what to do.",
    "REFRAMING": "The user needs help examining thoughts and perspective.",
    "PROBLEM_SOLVING": "The user needs a structured next action or decision path.",
    "STORY": "The user wants comfort through a short story, metaphor, or example.",
    "VENTING": "The user mainly wants space to express pain before deeper guidance.",
    "MEDICAL_CHECK": "The user mentions physical symptoms that should not be dismissed.",
    "EXPLORATION": "The user is unclear and needs gentle clarification.",
}

INTENSITY_HIGH_PATTERNS = [
    r"\bpanic\b",
    r"\bcan't breathe\b",
    r"\bchest pain\b",
    r"\bheart racing\b",
    r"\bshaking\b",
    r"\bhelp me now\b",
    r"\bcalm me\b",
    r"\bamar buk\b",
    r"\bbuke byatha\b",
    r"\bdom bondho\b",
]

MEDICAL_PATTERNS = [
    r"\bchest pain\b",
    r"\bchest tight\b",
    r"\bfaint\b",
    r"\bpassed out\b",
    r"\bsevere pain\b",
    r"\bcan't breathe\b",
    r"\bbreathing pain\b",
    r"\bbuke byatha\b",
    r"\bshash nite parchi na\b",
]

STORY_PATTERNS = [
    r"\bstory\b",
    r"\bmetaphor\b",
    r"\bexample\b",
    r"\bgolpo\b",
    r"\bউদাহরণ\b",
]

ADVICE_PATTERNS = [
    r"\bwhat should i do\b",
    r"\bwhat do i do\b",
    r"\bki korbo\b",
    r"\bwhat can i do\b",
    r"\bhelp me decide\b",
]

VENTING_PATTERNS = [
    r"\bjust listen\b",
    r"\blet me vent\b",
    r"\bshudhu shuno\b",
    r"\bi want to say everything\b",
]

CALMING_PATTERNS = [
    r"\bpanic\b",
    r"\bcalm me\b",
    r"\bground me\b",
    r"\bbreathing\b",
    r"\bamar buk\b",
    r"\bdom bondho\b",
    r"\bshash\b",
]

REFRAMING_PATTERNS = [
    r"\boverthinking\b",
    r"\bwhat if\b",
    r"\bintrusive\b",
    r"\bthoughts won't stop\b",
    r"\bmatha theke jacche na\b",
]

PROBLEM_SOLVING_PATTERNS = [
    r"\bdecide\b",
    r"\boption\b",
    r"\bproblem\b",
    r"\bplan\b",
    r"\bfigure out\b",
]


def detect_current_need(user_content: str, category_name: Optional[str] = None) -> str:
    text = (user_content or "").strip().lower()

    if _matches_any(text, MEDICAL_PATTERNS):
        return "MEDICAL_CHECK"
    if _matches_any(text, STORY_PATTERNS):
        return "STORY"
    if _matches_any(text, ADVICE_PATTERNS):
        return "ADVICE"
    if _matches_any(text, VENTING_PATTERNS):
        return "VENTING"
    if _matches_any(text, CALMING_PATTERNS) or category_name == "Panic Attacks":
        return "CALMING"
    if _matches_any(text, PROBLEM_SOLVING_PATTERNS) or category_name == "Workplace Stress":
        return "PROBLEM_SOLVING"
    if _matches_any(text, REFRAMING_PATTERNS) or category_name in {"General Anxiety", "OCD / Intrusive Thoughts", "Social Anxiety"}:
        return "REFRAMING"
    if category_name in {"Depression", "Grief & Loss", "Relationship / Family"}:
        return "VALIDATION"
    return "EXPLORATION"


def detect_intensity(user_content: str) -> str:
    text = (user_content or "").strip().lower()
    if _matches_any(text, INTENSITY_HIGH_PATTERNS):
        return "high"
    if len(text) < 30:
        return "medium"
    return "low"


def determine_response_style(current_need: str, intensity: str) -> str:
    if current_need in {"CALMING", "MEDICAL_CHECK"}:
        return "brief_grounding"
    if current_need == "STORY":
        return "comforting_story"
    if current_need == "PROBLEM_SOLVING":
        return "structured_coaching"
    if current_need == "REFRAMING":
        return "gentle_cbt"
    if current_need == "VENTING":
        return "listening_first"
    if intensity == "high":
        return "very_short_support"
    return "warm_reflective"


def build_support_plan(
    user_content: str,
    category_name: Optional[str],
    protocol_text: str,
    recent_interventions: Optional[List[str]] = None,
) -> Dict[str, str]:
    current_need = detect_current_need(user_content, category_name)
    intensity = detect_intensity(user_content)
    response_style = determine_response_style(current_need, intensity)
    next_step = choose_next_step(category_name, current_need, intensity, recent_interventions or [])
    button_hints = suggested_button_hints(category_name, current_need, intensity)

    return {
        "current_need": current_need,
        "intensity": intensity,
        "response_style": response_style,
        "next_step": next_step,
        "protocol_text": protocol_text,
        "button_hints": ", ".join(button_hints),
    }


def choose_next_step(
    category_name: Optional[str],
    current_need: str,
    intensity: str,
    recent_interventions: List[str],
) -> str:
    recent = {item.strip().lower() for item in recent_interventions if item}

    if current_need == "MEDICAL_CHECK":
        return "Acknowledge the fear, avoid assuming it is only anxiety, and gently advise medical help if symptoms are new, severe, or unsafe before continuing emotional support."
    if current_need == "STORY":
        return "Give a short healing story or metaphor that mirrors the user's emotional pain, then connect it back to their present moment."
    if current_need == "VENTING":
        return "Reflect the emotional pain first and ask one focused question before offering any exercise."
    if current_need == "CALMING":
        if "grounding" not in recent:
            return "Start with one grounding step only, such as noticing the room, feet on the floor, or one slow breath cycle."
        return "After grounding, ask what is happening in the body right now and keep the reply short."
    if current_need == "ADVICE":
        return "Give one practical next step only, not a long list, and ask if they want a second step after that."
    if current_need == "PROBLEM_SOLVING":
        return "Define the immediate problem in one sentence, then help the user choose one small action."
    if current_need == "REFRAMING":
        if category_name == "OCD / Intrusive Thoughts":
            return "Label the thought without arguing with it, reduce reassurance, and invite a brief defusion step."
        return "Name the main thought, separate facts from fear, and offer one balanced alternative perspective."
    if category_name == "Depression":
        return "Focus on one tiny doable action and avoid overwhelming the user with many tasks."
    if category_name == "Relationship / Family":
        return "Validate the hurt, clarify what happened, and explore what the user wishes had been different."
    if category_name == "Grief & Loss":
        return "Make space for the sadness without trying to fix it too fast, then ask what feels heaviest today."
    return "Validate the emotional pain, choose one simple support step, and ask one question that keeps the conversation moving."


def suggested_button_hints(category_name: Optional[str], current_need: str, intensity: str) -> List[str]:
    if current_need == "MEDICAL_CHECK":
        return ["Describe the symptoms", "Slow breathing", "Could this need medical help?"]
    if current_need == "STORY":
        return ["Another short story", "Talk about this feeling", "One small step"]
    if current_need == "CALMING" or category_name == "Panic Attacks":
        return ["Slow breathing", "Try grounding", "What am I feeling in my body?"]
    if current_need == "PROBLEM_SOLVING":
        return ["Define the problem", "Pick one small action", "Help me decide"]
    if current_need == "REFRAMING":
        return ["Name the thought", "Check the evidence", "Help me slow down"]
    if category_name == "Relationship / Family":
        return ["Tell what happened", "What do I want to say?", "Help me calm down first"]
    if category_name == "Depression":
        return ["Pick one tiny step", "Let me describe today", "Just stay with me"]
    if intensity == "high":
        return ["Stay with me", "Slow breathing", "One step at a time"]
    return ["Tell you more", "What would help right now?", "Give me one small step"]


def _matches_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
