import logging
import re
from typing import Any, Dict
from .llm import call_agent_llm

logger = logging.getLogger("chat.safety")

# =====================================================================
# TIER 1: FAST DETERMINISTIC REGEX SHIELD (English + Bengali)
# =====================================================================
CRISIS_KEYWORDS = [
    # English explicit
    r"\bsuicide\b",
    r"\bkill myself\b",
    r"\bwant to die\b",
    r"\bend my life\b",
    r"\bend it all\b",
    r"\bself-harm\b",
    r"\bhurt myself\b",
    r"\bcutting myself\b",
    r"\boverdose\b",
    r"\bhang myself\b",
    r"\bslit my wrists\b",
    r"\bbetter off dead\b",
    r"\bno reason to live\b",
    r"\bswallow pills\b",
    r"\bjump off\b",
    
    # Bengali explicit (বাংলা)
    r"আত্মহত্যা",
    r"মরে যেতে চাই",
    r"মরতে চাই",
    r"বাঁচতে চাই না",
    r"বাঁচতে ইচ্ছে করে না",
    r"সব শেষ করে দিতে চাই",
    r"সব শেষ করে দেব",
    r"গলায় দড়ি",
    r"বিষ খেয়ে",
    r"নিজেকে শেষ",
    r"নিজেকে আঘাত",
    r"আর বাঁচবো না",
    r"জীবন শেষ",
]

# Triggers that warrant a deeper Tier 2 semantic check
SEMANTIC_CHECK_TRIGGERS = [
    r"\bgive away\b",
    r"\bgiving away my\b",
    r"\bsleep forever\b",
    r"\bnever wake up\b",
    r"\bno point anymore\b",
    r"\beveryone better without me\b",
    r"\bgoodbye everyone\b",
    r"\bfinal goodbye\b",
    r"চিরতরে ঘুমিয়ে",
    r"বিদায় পৃথিবী",
    r"আর কোনো আশা নেই",
]


def check_for_crisis_tier1(content: str) -> bool:
    """
    Tier-1 Fast Regex check (0ms). Returns True if direct crisis phrases match.
    """
    if not content:
        return False
        
    for pattern in CRISIS_KEYWORDS:
        if re.search(pattern, content, re.IGNORECASE):
            logger.warning("Safety Tier-1 Regex matched: %s", pattern)
            return True
            
    return False


def check_semantic_crisis(content: str) -> bool:
    """
    Tier-2 Fast Semantic Safety Evaluation (uses LLM guard to catch disguised or metaphorical suicidal intent).
    """
    if not content or len(content.strip()) < 8:
        return False

    prompt = (
        "You are a clinical safety classifier. Evaluate the following message for suicidal intent, "
        "severe self-harm, or disguised farewell/giving up on life (including metaphorical speech or Bengali).\n\n"
        f"Message: \"{content}\"\n\n"
        "Return exactly one word: 'CRISIS' if there is any indication of self-harm, suicide, or wanting to die; "
        "otherwise return 'SAFE'."
    )

    try:
        choice = call_agent_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        verdict = (choice.content or "").strip().upper()
        is_crisis = "CRISIS" in verdict
        if is_crisis:
            logger.warning("Safety Tier-2 Semantic Guard triggered: verdict=%s", verdict)
        return is_crisis
    except Exception as exc:
        logger.error("Tier-2 semantic safety check failed: %s", exc)
        return False


def check_for_crisis(content: str) -> bool:
    """
    Comprehensive two-tier crisis check.
    Returns True if either Tier 1 (regex) or Tier 2 (semantic trigger) confirms crisis.
    """
    # 1. Tier 1 fast deterministic check
    if check_for_crisis_tier1(content):
        return True

    # 2. Check if text contains subtle farewell/despair triggers
    for pattern in SEMANTIC_CHECK_TRIGGERS:
        if re.search(pattern, content, re.IGNORECASE):
            logger.info("Semantic trigger matched: %s. Running Tier-2 guard...", pattern)
            return check_semantic_crisis(content)

    return False


def get_emergency_response() -> Dict[str, Any]:
    """
    Returns fallback crisis dictionary for legacy compatibility.
    """
    return {
        "empathetic_response": (
            "I'm deeply concerned about your safety right now. Please know that you are not alone. "
            "Please call emergency services (999 in Bangladesh) or reach out to Kaan Pete Roi (+8801779554391) immediately."
        ),
        "detected_category": "Crisis",
        "confidence_score": 1.0,
        "suggested_buttons": ["Emergency 999", "Call a Friend", "Kaan Pete Roi"],
        "is_crisis": True,
    }
