from ..models import ChatSession, ProblemCategory, ChatMessage
from .llm import call_llm
from .chat_services import create_user_message, create_assistant_message
from .safety import check_for_crisis, get_emergency_response
from .protocols import get_protocol_for_category

INTAKE_SYSTEM_PROMPT_TEMPLATE = """
You are a compassionate, non-judgmental clinical intake assistant for a mental health app. 
Your goal is to validate the user's feelings and identify their primary concern.

Available Categories from our support database:
{category_list}

Rules:
1. Be extremely empathetic and validation-focused.
2. LANGUAGE RULE: Detect the user's language (English or Bengali) and respond in the SAME language. 
   If the user speaks Bengali (Bangla), you MUST respond in Bengali characters.
3. If the user is vague, ask ONE open-ended question to clarify.
4. For detected_category, use exactly one category name from the database list above, or null if unclear.
5. Always return your analysis in the specified JSON format.
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


def handle_user_input(session_id, user_content, audio_path=None):
    """
    Orchestrates the response generation.
    """
    # 1. Fetch Session
    session = ChatSession.objects.get(id=session_id)
    history = []
    
    # 2. Deterministic Safety Check
    if check_for_crisis(user_content):
        session.current_flow = "crisis"
        session.save()
        analysis = get_emergency_response()
    else:
        # 3. Save User Message
        create_user_message(session_id, user_content)
        
        # 4. Prepare History for context
        history_msgs = ChatMessage.objects.filter(session=session).order_by('created_at')[:10]
        history = [{"role": msg.sender, "content": msg.content} for msg in history_msgs]
        
        # 5. Select Strategy based on Flow
        if session.current_flow == "discovery":
            system_prompt = _get_intake_system_prompt()
        elif session.current_flow == "active_support" and session.problem_category:
            protocol_text = get_protocol_for_category(session.problem_category)
            system_prompt = (
                f"You are supporting a user with {session.problem_category.name}. {protocol_text}\n"
                "LANGUAGE RULE: Respond in the SAME language as the user. If they speak Bengali, respond in Bengali characters."
            )
            
            # Contextual suggestions
            support_msg_count = ChatMessage.objects.filter(session=session, sender="assistant").count()
            if support_msg_count >= 3:
                system_prompt += " Suggest starting our 7-day micro-workplan if the user feels ready."
        else:
            system_prompt = "Be a supportive listener. Detect and match the user's language (Bengali or English)."

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

    # 8. Category Transition Logic
    detected_cat_name = analysis.get("detected_category")
    confidence = analysis.get("confidence_score", 0)
    
    if detected_cat_name and confidence > 0.8 and session.current_flow == "discovery":
        category = _find_problem_category(detected_cat_name)
        if category:
            session.problem_category = category
            session.current_flow = "active_support"
            session.save()
            protocol_text = get_protocol_for_category(category)
            support_prompt = (
                f"You are supporting a user with {category.name}. {protocol_text}\n"
                "LANGUAGE RULE: Respond in the SAME language as the user. If they speak Bengali, respond in Bengali characters.\n"
                "Keep the response short, practical, and guided. Start with one small next step."
            )
            analysis = call_llm(
                system_prompt=support_prompt,
                user_message=user_content,
                history=history
            )
            detected_cat_name = category.name
            confidence = max(confidence, analysis.get("confidence_score", 0))

    # 9. Return the complete response
    return create_assistant_message(
        session_id,
        content=analysis.get("empathetic_response"),
        suggested_replies=analysis.get("suggested_buttons"),
        metadata={"category": detected_cat_name, "confidence": confidence}
    )
