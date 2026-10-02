import json
import logging
import os
from typing import Any, Dict, List, Optional

from groq import Groq


logger = logging.getLogger("chat.llm")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_CHAT_MODEL = (
    os.getenv("GROQ_CHAT_MODEL")
    or os.getenv("GROQ_MODEL")
    or "openai/gpt-oss-120b"
)
# Fallback to high-capability Groq model if llama-3.3 is not enabled on account
if GROQ_CHAT_MODEL == "llama-3.3-70b-versatile":
    GROQ_CHAT_MODEL = "openai/gpt-oss-120b"

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
Rules for the JSON fields:
- empathetic_response must sound warm, human, and specific to the user's exact situation.
- empathetic_response must be short to medium length, usually 2 to 5 sentences, unless the user explicitly asks for more.
- empathetic_response must end with a clear question every time.
- If the user asks for a short story, metaphor, example, or script, provide it naturally inside empathetic_response.
- suggested_buttons must be tailored to the user's current state, not generic repeated options.
- suggested_buttons must contain 2 to 4 concise options.
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
            temperature=0.7,
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


def call_agent_llm(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.7,
    model: Optional[str] = None,
) -> Any:
    """
    Calls Groq chat completion with native function/tool calling enabled.
    Returns the message object from response.choices[0].message:
      - .content: text response from the model (or None if only tools were called)
      - .tool_calls: list of tool calls requested by the model (or None)
    """
    if not client:
        raise RuntimeError("Groq client is not initialized. Please verify GROQ_API_KEY.")

    target_model = model or GROQ_CHAT_MODEL

    kwargs: Dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature,
    }

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    logger.debug(
        "Calling Groq agent completion | model=%s | message_count=%d | tools_count=%d",
        target_model,
        len(messages),
        len(tools) if tools else 0,
    )

    response = client.chat.completions.create(**kwargs)
    choice = response.choices[0].message

    if choice.tool_calls:
        logger.info(
            "Groq agent requested tool execution | model=%s | tool_calls=%s",
            target_model,
            [tc.function.name for tc in choice.tool_calls],
        )
    else:
        logger.info(
            "Groq agent generated direct response | model=%s | preview=%s",
            target_model,
            (choice.content or "")[:100],
        )

    return choice

