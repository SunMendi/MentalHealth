import json
import logging
import os
from typing import Any, Dict, List

from groq import Groq


logger = logging.getLogger("chat.llm")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    logger.error("CRITICAL: GROQ_API_KEY is missing for chat generation!")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


JSON_RESPONSE_INSTRUCTIONS = """
Return valid JSON with exactly these keys:
- empathetic_response: string
- detected_category: string or null
- confidence_score: number between 0 and 1
- suggested_buttons: array of short strings
- is_crisis: boolean
Do not wrap the JSON in markdown.
"""


def _extract_json_payload(content: str) -> Dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def call_llm(system_prompt: str, user_message: str, history: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    """
    Calls Groq chat completions for structured mental-health support responses.
    """
    if not client:
        return {
            "empathetic_response": "I'm having a technical connection issue. Please check your internet or try again. (Bengali: আমার সংযোগে কিছুটা সমস্যা হচ্ছে। দয়া করে আবার চেষ্টা করুন।)",
            "detected_category": None,
            "confidence_score": 0.0,
            "suggested_buttons": ["Try again"],
            "is_crisis": False,
        }

    try:
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": f"{system_prompt}\n\n{JSON_RESPONSE_INSTRUCTIONS}",
            }
        ]

        for item in history or []:
            role = item.get("role")
            if role == "user":
                mapped_role = "user"
            elif role == "assistant":
                mapped_role = "assistant"
            else:
                continue
            messages.append(
                {
                    "role": mapped_role,
                    "content": item.get("content", ""),
                }
            )

        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=messages,
            temperature=0.4,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content if response and response.choices else ""
        if not content:
            raise ValueError("Groq returned an empty response")

        parsed = _extract_json_payload(content)
        logger.info(
            "Groq chat generation successful | model=%s | response_preview=%s",
            GROQ_CHAT_MODEL,
            str(parsed)[:200],
        )
        return parsed

    except Exception as e:
        logger.exception("Groq chat generation failed | model=%s | error=%s", GROQ_CHAT_MODEL, e)
        error_msg = str(e).lower()
        if "429" in error_msg or "rate limit" in error_msg or "quota" in error_msg:
            return {
                "empathetic_response": "I'm receiving too many messages right now. Please wait a few seconds and try again. (Bengali: আমি এই মুহূর্তে অনেক বার্তা পাচ্ছি। দয়া করে কয়েক সেকেন্ড অপেক্ষা করুন।)",
                "detected_category": None,
                "confidence_score": 0.0,
                "suggested_buttons": ["Wait and retry"],
                "is_crisis": False,
            }

        return {
            "empathetic_response": "I'm having a technical connection issue. Please check your internet or try again. (Bengali: আমার সংযোগে কিছুটা সমস্যা হচ্ছে। দয়া করে আবার চেষ্টা করুন।)",
            "detected_category": None,
            "confidence_score": 0.0,
            "suggested_buttons": ["Try again"],
            "is_crisis": False,
        }
