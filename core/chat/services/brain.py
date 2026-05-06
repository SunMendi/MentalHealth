import logging
from ..models import ChatSession, ProblemCategory, ChatMessage
from .llm import call_llm
from .chat_services import create_user_message, create_assistant_message
from .safety import check_for_crisis, get_emergency_response
from .protocols import get_protocol_for_category
from .plans import activate_plan
from .support_planner import build_support_plan

logger = logging.getLogger("chat.brain")

INTAKE_SYSTEM_PROMPT_TEMPLATE = """
You are a compassionate, non-judgmental mental health support guide for a guided support app.
Your goal is to understand the user's immediate emotional problem, respond like a calm realistic psychologist, and identify the primary concern so we can route them well.

Available Categories from our support database:
{category_list}

Rules:
1. Be deeply empathetic, concrete, and natural. Avoid robotic therapy phrases.
2. LANGUAGE RULE: Respond in the SAME language as the user. If they write in Bangla, answer in Bangla.
3. DECISIVENESS: If the user mentions a clear issue like panic, overthinking, relationship stress, intrusive thoughts, sadness, grief, work stress, anger, or loneliness, choose the closest category immediately.
4. MANDATORY GUIDANCE: EVERY response must end with a clear question that keeps the conversation going.
5. Ask only one focused follow-up question at a time.
6. Avoid repeating the same suggestions from earlier turns unless the user says a previous step helped.
7. If the user asks for a short story, metaphor, script, or example, provide one that fits their exact emotional state.
8. If the user mentions chest pain, trouble breathing, fainting, or severe physical symptoms, do not dismiss it as only emotional. Briefly suggest getting medical help if symptoms are new, severe, or feel unsafe.
9. Always return your analysis in the specified JSON format.
"""

SUPPORT_STYLE_RULES = """
You are not a free-chat bot. You are a guided emotional support companion.

Response quality rules:
- Sound like a skilled, warm psychologist, but do not claim to be a doctor or therapist.
- Be specific to the user's words. Reflect what they actually said.
- Use short, clear paragraphs and practical steps.
- Never give the exact same 3 or 4 suggestions repeatedly.
- Match intensity: panic needs short grounding, sadness needs warmth, overthinking needs structure, relationship pain needs validation and careful reflection.
- If the user asks for comfort through a story, give a short healing story or metaphor rather than refusing or giving a dry explanation.
- Always end with exactly one question that invites the next reply.
- Do not end the conversation. There is always a next step or next question.

Suggestion button rules:
- Give 2 to 4 options only.
- Buttons must fit the current moment, not generic repeated choices.
- Prefer action-oriented or emotionally-relevant options.
"""


def _build_category_context() -> str:
    categories = ProblemCategory.objects.all().order_by("name")
    if not categories:
        return "- General: broad emotional support when no category data is available"

    return "\n".join(
        f"- {category.name}: {category.description or 'No description provided.'}"
        for category in categories
    )


def _get_intake_system_prompt() -> str:
    return INTAKE_SYSTEM_PROMPT_TEMPLATE.format(category_list=_build_category_context())


def _find_problem_category(category_name):
    if not category_name:
        return None

    normalized_name = str(category_name).strip()
    category = ProblemCategory.objects.filter(name__iexact=normalized_name).first()
    if category:
        return category

    # Safety net for older model outputs like "Anxiety" when DB has "General Anxiety".
    return ProblemCategory.objects.filter(name__icontains=normalized_name).first()


def _looks_bengali(text: str) -> bool:
    return any("\u0980" <= ch <= "\u09FF" for ch in (text or ""))


def _recent_assistant_text(session, limit=4):
    return list(
        ChatMessage.objects.filter(session=session, sender="assistant")
        .order_by("-created_at")
        .values_list("content", flat=True)[:limit]
    )


def _recent_suggested_replies(session, limit=4):
    recent_messages = (
        ChatMessage.objects.filter(session=session, sender="assistant")
        .order_by("-created_at")[:limit]
    )
    recent = []
    for msg in recent_messages:
        for item in msg.suggested_replies or []:
            normalized = str(item).strip()
            if normalized:
                recent.append(normalized)
    return recent


def _recent_interventions(session, limit=4):
    recent_messages = (
        ChatMessage.objects.filter(session=session, sender="assistant")
        .order_by("-created_at")[:limit]
    )
    recent = []
    for msg in recent_messages:
        intervention = (msg.metadata or {}).get("next_step")
        if intervention:
            recent.append(str(intervention))
    return recent


def _build_contextual_prompt(session, user_content, history, support_plan):
    recent_reply_text = "\n".join(f"- {text}" for text in _recent_assistant_text(session))
    recent_buttons = "\n".join(f"- {item}" for item in _recent_suggested_replies(session))
    recent_steps = "\n".join(f"- {item}" for item in _recent_interventions(session))
    history_excerpt = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in history[-6:]
    )

    category_name = session.problem_category.name if session.problem_category else "Unknown"
    protocol_text = support_plan["protocol_text"]

    return (
        f"{SUPPORT_STYLE_RULES}\n\n"
        f"Current session flow: {session.current_flow}\n"
        f"Current category: {category_name}\n"
        f"Current user need: {support_plan['current_need']} - {support_plan['response_style']}\n"
        f"Intensity level: {support_plan['intensity']}\n"
        f"Required next step: {support_plan['next_step']}\n"
        f"Protocol guidance: {protocol_text}\n\n"
        f"Recent conversation excerpt:\n{history_excerpt or '- No prior history'}\n\n"
        f"Recent intervention steps to avoid repeating too closely:\n{recent_steps or '- None'}\n\n"
        f"Recent assistant replies to avoid repeating too closely:\n{recent_reply_text or '- None'}\n\n"
        f"Recent suggestion buttons to avoid repeating too closely:\n{recent_buttons or '- None'}\n\n"
        f"Current user message:\n{user_content}\n\n"
        f"Button direction for this turn: {support_plan['button_hints']}"
    )


def _ensure_question(text: str, is_bengali: bool) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "Can you tell me a little more about what feels hardest right now?" if not is_bengali else "এই মুহূর্তে কোন জিনিসটা আপনার কাছে সবচেয়ে কঠিন লাগছে?"

    if "?" in cleaned[-3:]:
        return cleaned

    follow_up = (
        " What feels most intense for you right now?"
        if not is_bengali
        else " এই মুহূর্তে কোন জিনিসটা সবচেয়ে বেশি কষ্ট দিচ্ছে?"
    )
    return f"{cleaned}{follow_up}"


def _fallback_buttons(user_content: str, category_name: str | None, is_bengali: bool):
    text = (user_content or "").lower()
    if "story" in text or "golpo" in text:
        return (
            ["আরেকটা ছোট গল্প", "এটা নিয়ে কথা বলি", "এখন কী করব?"]
            if is_bengali
            else ["Another short story", "Let's talk about this feeling", "What can I do right now?"]
        )
    if "chest" in text or "breath" in text or "buk" in text:
        return (
            ["শ্বাস ধীরে নেই", "লক্ষণগুলো বলি", "মেডিকেল সাহায্য লাগতে পারে?"]
            if is_bengali
            else ["Let's slow your breathing", "Describe the symptoms", "Could this need medical help?"]
        )
    if category_name == "Panic Attacks":
        return (
            ["৫-৪-৩-২-১ করি", "শ্বাস ধীরে নেই", "আমি এখন কী অনুভব করছি?"]
            if is_bengali
            else ["Try 5-4-3-2-1", "Slow breathing", "What am I feeling in my body?"]
        )
    if category_name == "General Anxiety":
        return (
            ["চিন্তাটা ধরতে চাই", "প্রমাণ দেখি", "এখন শান্ত হওয়া দরকার"]
            if is_bengali
            else ["Name the worry", "Check the evidence", "I need calm first"]
        )
    if category_name == "Relationship / Family":
        return (
            ["কী হয়েছিল বলি", "আমি কী বলতে চাই?", "আগে নিজেকে শান্ত করি"]
            if is_bengali
            else ["Tell what happened", "What do I want to say?", "Help me calm down first"]
        )
    if category_name == "Depression":
        return (
            ["একটা ছোট কাজ বেছে নেই", "আজ কেমন লাগছে বলি", "শুধু পাশে থাকুন"]
            if is_bengali
            else ["Pick one tiny step", "Let me describe today", "Just stay with me"]
        )
    return (
        ["আরও বলি", "এখন কী করলে ভালো হবে?", "একটা ছোট step দাও"]
        if is_bengali
        else ["Tell you more", "What would help right now?", "Give me one small step"]
    )


def _dedupe_buttons(buttons, recent_buttons, fallback_buttons):
    normalized_recent = {item.strip().lower() for item in recent_buttons if item}
    deduped = []
    for item in buttons or []:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        if cleaned.lower() in normalized_recent:
            continue
        if cleaned.lower() in {x.lower() for x in deduped}:
            continue
        deduped.append(cleaned)
        if len(deduped) == 4:
            break

    for item in fallback_buttons:
        if len(deduped) == 4:
            break
        if item.lower() in normalized_recent:
            continue
        if item.lower() in {x.lower() for x in deduped}:
            continue
        deduped.append(item)

    return deduped[:4]


def _merge_button_fallbacks(plan_hints: str, fallback_buttons):
    merged = []
    for item in (plan_hints or "").split(","):
        cleaned = item.strip()
        if cleaned:
            merged.append(cleaned)

    for item in fallback_buttons:
        if item.lower() in {x.lower() for x in merged}:
            continue
        merged.append(item)

    return merged


def handle_user_input(session_id, user_content, audio_path=None):
    """
    Orchestrates the response generation.
    """
    # 1. Fetch Session
    session = ChatSession.objects.get(id=session_id)
    history = []
    is_bengali = _looks_bengali(user_content)
    support_plan = None
    
    # 2. Deterministic Safety Check
    if check_for_crisis(user_content):
        session.current_flow = "crisis"
        session.save()
        analysis = get_emergency_response()
    else:
        # 3. Save User Message
        create_user_message(session_id, user_content)
        
        # 4. Prepare History for context (Get last 10 messages)
        history_msgs = (
            ChatMessage.objects.filter(session=session)
            .order_by("-created_at")[:10]
        )
        # Reverse to maintain chronological order for the LLM
        history = [
            {"role": msg.sender, "content": msg.content} 
            for msg in reversed(list(history_msgs))
        ]
        
        # 5. Select Strategy based on Flow
        category_for_planning = session.problem_category.name if session.problem_category else None
        protocol_text = get_protocol_for_category(session.problem_category) if session.problem_category else "Provide grounded emotional support and identify the closest support path."
        support_plan = build_support_plan(
            user_content=user_content,
            category_name=category_for_planning,
            protocol_text=protocol_text,
            recent_interventions=_recent_interventions(session),
        )

        if session.current_flow == "discovery":
            system_prompt = (
                f"{_get_intake_system_prompt()}\n\n"
                f"Current need the user seems to have: {support_plan['current_need']}\n"
                f"Suggested response style: {support_plan['response_style']}\n"
                f"Immediate next step: {support_plan['next_step']}"
            )
        elif session.current_flow == "active_support" and session.problem_category:
            system_prompt = _build_contextual_prompt(session, user_content, history, support_plan)
            
            # Contextual suggestions
            support_msg_count = ChatMessage.objects.filter(session=session, sender="assistant").count()
            if support_msg_count >= 3:
                system_prompt += "\nIf appropriate, gently mention the 7-day micro-workplan only once in a while, not in every message."
        else:
            system_prompt = _build_contextual_prompt(session, user_content, history, support_plan)

        # 6. Call Groq text generation using the already-transcribed user text.
        analysis = call_llm(
            system_prompt=system_prompt,
            user_message=user_content,
            history=history
        )
    
    # 7. Crisis Handling
    if analysis.get("is_crisis"):
        session.current_flow = "crisis"
        session.save()

    # 8. Category Transition Logic (The Pivot)
    detected_cat_name = analysis.get("detected_category")
    confidence = analysis.get("confidence_score", 0)
    
    # Lower threshold from 0.8 to 0.7 for faster detection when user is clear
    if detected_cat_name and confidence >= 0.7 and session.current_flow == "discovery":
        category = _find_problem_category(detected_cat_name)
        if category:
            # Acknowledge the problem and trigger the plan
            session.problem_category = category
            session.current_flow = "active_support"
            session.save()
            
            # AUTOMATED PLAN ACTIVATION
            if session.user:
                try:
                    activate_plan(session.user, category.id)
                    logger.info("7-day plan automatically activated | user_id=%s | category=%s", session.user.id, category.name)
                except Exception as e:
                    logger.error("Failed to auto-activate plan: %s", e)
            else:
                logger.info("Plan activation skipped: Session has no associated user")

            # Protocol-driven response for immediate relief
            protocol_text = get_protocol_for_category(category)
            support_plan = build_support_plan(
                user_content=user_content,
                category_name=category.name,
                protocol_text=protocol_text,
                recent_interventions=_recent_interventions(session),
            )
            support_prompt = (
                f"The user is dealing with {category.name}. You have just transitioned them to active support. "
                f"1. Acknowledge their situation with deep empathy. "
                f"2. EXPLICITLY MENTION: 'I've created a gentle 7-day support plan for you based on this. You can find it in your Daily Plan whenever you're ready.' "
                f"3. IMMEDIATELY PIVOT to the current moment: 'But for right now, let's focus on what's happening. I want to try a simple {category.name} exercise with you.' "
                f"4. PROTOCOL: {protocol_text}. "
                f"5. Current need: {support_plan['current_need']}. "
                f"6. Response style: {support_plan['response_style']}. "
                f"7. Required next step: {support_plan['next_step']}. "
                f"Rules:\n"
                f"- Be short and practical.\n"
                f"- Start with only the FIRST step of the protocol.\n"
                f"- MANDATORY GUIDANCE: You MUST end your message with a question or a prompt that asks the user if they are ready or how they feel about the step. Never end with a statement.\n"
                f"- LANGUAGE RULE: Match the user's language (Bengali for Bengali).\n"
                f"- Do not reuse the same suggestion buttons from the last few turns.\n"
                f"- If the user asked for a short story, comforting example, or metaphor, include it naturally.\n"
                f"- If the user mentions chest pain or severe physical symptoms, briefly suggest medical help if it feels new, severe, or unsafe.\n\n"
                f"{SUPPORT_STYLE_RULES}"
            )
            
            analysis = call_llm(
                system_prompt=support_prompt,
                user_message=user_content,
                history=history
            )
            detected_cat_name = category.name
            confidence = max(confidence, analysis.get("confidence_score", 0))

    # 9. Return the complete response
    detected_cat_name = detected_cat_name or analysis.get("detected_category")
    response_text = _ensure_question(analysis.get("empathetic_response"), is_bengali)
    recent_buttons = _recent_suggested_replies(session)
    fallback_buttons = _fallback_buttons(user_content, detected_cat_name, is_bengali)
    if support_plan is None:
        protocol_text = get_protocol_for_category(session.problem_category) if session.problem_category else "Provide grounded emotional support and identify the closest support path."
        support_plan = build_support_plan(
            user_content=user_content,
            category_name=detected_cat_name,
            protocol_text=protocol_text,
            recent_interventions=_recent_interventions(session),
        )
    merged_fallback_buttons = _merge_button_fallbacks(support_plan.get("button_hints"), fallback_buttons)
    suggested_replies = _dedupe_buttons(
        analysis.get("suggested_buttons"),
        recent_buttons=recent_buttons,
        fallback_buttons=merged_fallback_buttons,
    )

    return create_assistant_message(
        session_id,
        content=response_text,
        suggested_replies=suggested_replies,
        metadata={
            "category": detected_cat_name,
            "confidence": confidence,
            "current_need": support_plan.get("current_need"),
            "response_style": support_plan.get("response_style"),
            "next_step": support_plan.get("next_step"),
            "intensity": support_plan.get("intensity"),
        }
    )
