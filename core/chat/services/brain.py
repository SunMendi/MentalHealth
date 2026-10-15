import logging
from typing import Any, Dict, Optional
from asgiref.sync import async_to_sync
from ..models import ChatSession, ProblemCategory, ChatMessage
from ..serializers import ChatMessageResponseSerializer
from .voice import generate_speech_base64
from .chat_services import create_user_message, create_assistant_message
from .safety import check_for_crisis
from .agent_runner import run_agent_loop_stream, _fallback_emotional_buttons
from ..agents import (
    triage_user_message,
    handle_panic_flow,
    handle_cbt_flow,
    handle_supportive_flow,
    handle_crisis_flow,
)
from ..agents.panic import PANIC_SYSTEM_PROMPT
from ..agents.cbt import CBT_SYSTEM_PROMPT
from ..agents.supportive import SUPPORTIVE_SYSTEM_PROMPT

logger = logging.getLogger("chat.brain")


def _looks_bengali(text: str) -> bool:
    return any("\u0980" <= ch <= "\u09FF" for ch in (text or ""))


def _ensure_question(text: str, is_bengali: bool) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return (
            "এই মুহূর্তে কোন জিনিসটা আপনার কাছে সবচেয়ে কঠিন লাগছে?"
            if is_bengali
            else "Can you tell me a little more about what feels hardest right now?"
        )

    if "?" in cleaned[-3:]:
        return cleaned

    follow_up = (
        " এই মুহূর্তে কোন জিনিসটা সবচেয়ে বেশি কষ্ট দিচ্ছে?"
        if is_bengali
        else " What feels most intense for you right now?"
    )
    return f"{cleaned}{follow_up}"


def _find_problem_category(category_name: Optional[str]) -> Optional[ProblemCategory]:
    if not category_name:
        return None
    normalized = str(category_name).strip()
    category = ProblemCategory.objects.filter(name__iexact=normalized).first()
    if category:
        return category
    return ProblemCategory.objects.filter(name__icontains=normalized).first()


def handle_user_input(session_id: int, user_content: str, audio_path: Optional[str] = None) -> ChatMessage:
    """
    Production AI Agent Orchestrator:
    1. Deterministic & Semantic Crisis Shield (Two-Tier Guardrails).
    2. Persist user message & fetch conversation context.
    3. Clinical Supervisor Triage (Intake & routing).
    4. Autonomous Subagent Execution with native Tool Calling (Panic, CBT, Supportive).
    5. Persist assistant response & return structured message.
    """
    session = ChatSession.objects.get(id=session_id)
    is_bengali = _looks_bengali(user_content)

    # =====================================================================
    # 1. SAFETY FIRST: TWO-TIER CRISIS GUARDRAIL
    # =====================================================================
    if check_for_crisis(user_content):
        session.current_flow = "crisis"
        session.save(update_fields=["current_flow"])
        
        create_user_message(session_id, user_content)
        crisis_result = handle_crisis_flow(user_content, user=session.user)

        return create_assistant_message(
            session_id,
            content=crisis_result.content,
            suggested_replies=crisis_result.suggested_replies,
            metadata={
                "agent_mode": "crisis",
                "is_crisis": True,
                "executed_tools": crisis_result.executed_tools,
            },
        )

    # =====================================================================
    # 2. SAVE USER MESSAGE & LOAD CONVERSATION MEMORY
    # =====================================================================
    create_user_message(session_id, user_content)

    history_msgs = (
        ChatMessage.objects.filter(session=session)
        .order_by("-created_at")[:10]
    )
    history = [
        {"role": msg.sender, "content": msg.content}
        for msg in reversed(list(history_msgs))
    ]

    # =====================================================================
    # 3. SUPERVISOR TRIAGE (Route to Specialist Subagent)
    # =====================================================================
    triage = triage_user_message(user_content, history=history)
    mode = triage.get("mode", "supportive")
    detected_cat_name = triage.get("detected_category")
    confidence = triage.get("confidence", 0.0)

    # Update session state if a clear category is identified
    if detected_cat_name and confidence >= 0.7:
        category = _find_problem_category(detected_cat_name)
        if category:
            session.problem_category = category
            session.current_flow = "active_support"
            session.save(update_fields=["problem_category", "current_flow"])

    # =====================================================================
    # 4. DISPATCH TO SPECIALIST SUBAGENT WITH TOOLS
    # =====================================================================
    if mode == "panic":
        agent_result = handle_panic_flow(
            user_message=user_content,
            session_history=history,
            user=session.user,
        )
    elif mode == "cbt":
        agent_result = handle_cbt_flow(
            user_message=user_content,
            session_history=history,
            user=session.user,
            category_name=detected_cat_name or "General Anxiety",
        )
    else:
        agent_result = handle_supportive_flow(
            user_message=user_content,
            session_history=history,
            user=session.user,
            category_name=detected_cat_name,
        )

    # =====================================================================
    # 5. POLISH AND PERSIST ASSISTANT RESPONSE
    # =====================================================================
    final_text = _ensure_question(agent_result.content, is_bengali)

    return create_assistant_message(
        session_id,
        content=final_text,
        suggested_replies=agent_result.suggested_replies,
        metadata={
            "agent_mode": mode,
            "category": detected_cat_name or (session.problem_category.name if session.problem_category else None),
            "confidence": confidence,
            "iterations": agent_result.iterations,
            "executed_tools": agent_result.executed_tools,
        },
    )


def handle_user_input_stream(session_id: int, user_content: str):
    """
    Streaming AI Agent Orchestrator:
    1. Deterministic Crisis Check:
       - If crisis: save user message & crisis assistant message, yield tokens, and finish.
    2. Save User Message & Load Context.
    3. Clinical Supervisor Triage.
    4. Autonomous Subagent Execution with token-by-token streaming & tool calling.
    5. Clean text, extract dynamic buttons, persist assistant message, and yield 'done'.
    """
    session = ChatSession.objects.get(id=session_id)
    is_bengali = _looks_bengali(user_content)

    # 1. Deterministic Crisis Shield
    if check_for_crisis(user_content):
        session.current_flow = "crisis"
        session.save(update_fields=["current_flow"])

        user_msg = create_user_message(session_id, user_content)
        crisis_result = handle_crisis_flow(user_content, user=session.user)

        assistant_msg = create_assistant_message(
            session_id,
            content=crisis_result.content,
            suggested_replies=crisis_result.suggested_replies,
            metadata={
                "agent_mode": "crisis",
                "is_crisis": True,
                "executed_tools": crisis_result.executed_tools,
            },
        )

        yield {
            "type": "user_message",
            "message": ChatMessageResponseSerializer(user_msg).data,
        }

        # Stream words for crisis message
        words = crisis_result.content.split(" ")
        for i, word in enumerate(words):
            token = word if i == 0 else " " + word
            yield {"type": "token", "content": token}

        yield {
            "type": "done",
            "assistant_message": ChatMessageResponseSerializer(assistant_msg).data,
            "suggested_buttons": crisis_result.suggested_replies,
            "audio_base64": None,
        }
        return

    # 2. Save User Message & Load Memory
    user_msg = create_user_message(session_id, user_content)
    yield {
        "type": "user_message",
        "message": ChatMessageResponseSerializer(user_msg).data,
    }

    history_msgs = (
        ChatMessage.objects.filter(session=session)
        .order_by("-created_at")[:10]
    )
    history = [
        {"role": msg.sender, "content": msg.content}
        for msg in reversed(list(history_msgs))
    ]

    # 3. Supervisor Triage
    triage = triage_user_message(user_content, history=history)
    mode = triage.get("mode", "supportive")
    detected_cat_name = triage.get("detected_category")
    confidence = triage.get("confidence", 0.0)

    if detected_cat_name and confidence >= 0.7:
        category = _find_problem_category(detected_cat_name)
        if category:
            session.problem_category = category
            session.current_flow = "active_support"
            session.save(update_fields=["problem_category", "current_flow"])

    yield {
        "type": "meta",
        "agent_mode": mode,
        "detected_category": detected_cat_name,
    }

    # 4. Select System Prompt and Temperature
    if mode == "panic":
        system_prompt = PANIC_SYSTEM_PROMPT
        temperature = 0.5
    elif mode == "cbt":
        system_prompt = CBT_SYSTEM_PROMPT
        temperature = 0.6
    else:
        system_prompt = SUPPORTIVE_SYSTEM_PROMPT
        temperature = 0.7

    # 5. Stream Subagent Execution
    accumulated_content = []
    buttons = []
    executed_tools = []
    iterations = 1

    for ev in run_agent_loop_stream(
        user_message=user_content,
        system_prompt=system_prompt,
        session_history=history,
        user=session.user,
        temperature=temperature,
    ):
        if ev["type"] == "token":
            accumulated_content.append(ev["content"])
            yield {"type": "token", "content": ev["content"]}
        elif ev["type"] == "agent_finished":
            buttons = ev.get("buttons") or []
            executed_tools = ev.get("executed_tools") or []
            iterations = ev.get("iterations") or 1

    raw_text = "".join(accumulated_content).strip()
    if not raw_text:
        raw_text = (
            "আমি আপনার পাশে আছি। একটি ধীর শ্বাস নিন। এখন কেমন অনুভব করছেন?"
            if is_bengali
            else "I am here with you. Let's take a slow breath together. How does your body feel right now?"
        )
        yield {"type": "token", "content": raw_text}

    if not buttons:
        buttons = _fallback_emotional_buttons(raw_text)

    final_text = _ensure_question(raw_text, is_bengali)
    if len(final_text) > len(raw_text):
        extra = final_text[len(raw_text):]
        yield {"type": "token", "content": extra}

    # 6. Persist Assistant Message
    assistant_msg = create_assistant_message(
        session_id,
        content=final_text,
        suggested_replies=buttons[:4],
        metadata={
            "agent_mode": mode,
            "category": detected_cat_name or (session.problem_category.name if session.problem_category else None),
            "confidence": confidence,
            "iterations": iterations,
            "executed_tools": executed_tools,
        },
    )

    # 7. Generate Voice TTS if possible
    audio_base64 = None
    try:
        tts_res = async_to_sync(generate_speech_base64)(final_text)
        if tts_res:
            audio_base64 = tts_res["base64"]
            metadata = dict(assistant_msg.metadata or {})
            metadata["tts_voice"] = tts_res["voice"]
            assistant_msg.metadata = metadata
            assistant_msg.save(update_fields=["metadata"])
    except Exception as exc:
        logger.warning("Assistant voice generation failed in stream: %s", exc)

    yield {
        "type": "done",
        "assistant_message": ChatMessageResponseSerializer(assistant_msg).data,
        "suggested_buttons": buttons[:4],
        "audio_base64": audio_base64,
    }

