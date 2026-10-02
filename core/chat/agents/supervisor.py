import json
import logging
import re
from typing import Any, Dict, List, Optional
from ..services.llm import call_agent_llm

logger = logging.getLogger("chat.agents.supervisor")

SUPERVISOR_SYSTEM_PROMPT = """You are a clinical triage supervisor for an AI mental health platform.
Your ONLY job is to analyze the user's emotional state and route them to the correct specialist subagent.

Available Subagent Modes:
1. "panic": Acute physical panic, hyperventilation, chest tightness, racing heart, sudden intense terror (needs DBT grounding).
2. "cbt": Overthinking, rumination, "what if" anxiety, cognitive distortions, catastrophizing (needs thought restructuring).
3. "supportive": Sadness, depression, low energy, burnout, loneliness, relationship stress, grief, venting (needs warmth & behavioral activation).
4. "crisis": Self-harm, suicide, wanting to end life, overdose, or feeling like giving up completely.

Valid Categories:
- "Panic Attacks"
- "General Anxiety"
- "Depression"
- "Workplace Stress"
- "Relationship / Family"
- "Grief & Loss"

Return VALID JSON ONLY with this exact schema:
{
  "mode": "panic" | "cbt" | "supportive" | "crisis",
  "detected_category": "Category Name" or null,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation"
}
"""

def triage_user_message(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Classifies the user's intent and routes to the appropriate specialist subagent.
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT}
    ]

    # Include brief recent history for context
    for item in (history or [])[-4:]:
        role = item.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": item.get("content", "")})

    messages.append({
        "role": "user",
        "content": f"Analyze this message and return the JSON routing decision:\n\"{user_message}\""
    })

    try:
        choice = call_agent_llm(messages=messages, temperature=0.1)
        raw_text = (choice.content or "").strip()
        
        # Clean markdown wrappers if present
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)

        data = json.loads(raw_text)
        mode = data.get("mode", "supportive").lower()
        if mode not in ("panic", "cbt", "supportive", "crisis"):
            mode = "supportive"

        logger.info("Supervisor triage decision: mode=%s | category=%s | confidence=%.2f",
                    mode, data.get("detected_category"), data.get("confidence", 0.0))

        return {
            "mode": mode,
            "detected_category": data.get("detected_category"),
            "confidence": float(data.get("confidence", 0.5)),
            "reasoning": data.get("reasoning", "")
        }

    except Exception as exc:
        logger.exception("Supervisor triage parsing failed, falling back to heuristic: %s", exc)
        # Fallback heuristic
        lower = user_message.lower()
        if any(w in lower for w in ("panic", "chest", "breathe", "shaking", "heart racing")):
            return {"mode": "panic", "detected_category": "Panic Attacks", "confidence": 0.8, "reasoning": "Heuristic fallback"}
        if any(w in lower for w in ("overthink", "worry", "anxious", "what if", "scared")):
            return {"mode": "cbt", "detected_category": "General Anxiety", "confidence": 0.8, "reasoning": "Heuristic fallback"}
        return {"mode": "supportive", "detected_category": None, "confidence": 0.5, "reasoning": "General support fallback"}
