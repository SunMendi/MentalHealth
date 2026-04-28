from ..models import ChatSession, ProblemCategory, ChatMessage
from .llm import call_llm
from .chat_services import create_user_message, create_assistant_message
from .safety import check_for_crisis, get_emergency_response
from .protocols import get_protocol_for_category

INTAKE_SYSTEM_PROMPT = """
You are a compassionate, non-judgmental clinical intake assistant for a mental health app. 
Your goal is to validate the user's feelings and identify their primary concern.

Available Categories: Anxiety, Panic, Stress, Depression, Grief, Relationship.

Rules:
1. Be extremely empathetic and validation-focused.
2. If the user is vague, ask ONE open-ended question to clarify.
3. Always return your analysis in the specified JSON format.
"""

def handle_user_input(session_id, user_content):
    # 1. Fetch Session
    session = ChatSession.objects.get(id=session_id)
    
    # 2. Deterministic Safety Check
    if check_for_crisis(user_content):
        session.current_flow = "crisis"
        session.save()
        analysis = get_emergency_response()
    else:
        # 3. Save User Message
        create_user_message(session_id, user_content)
        
        # 4. Prepare History for LLM
        history_msgs = ChatMessage.objects.filter(session=session).order_by('created_at')[:10]
        history = [{"role": msg.sender, "content": msg.content} for msg in history_msgs]
        
        # 5. Choose Prompt based on Flow
        if session.current_flow == "discovery":
            system_prompt = INTAKE_SYSTEM_PROMPT
        elif session.current_flow == "active_support" and session.problem_category:
            # Use the new Protocols service
            protocol_text = get_protocol_for_category(session.problem_category)
            system_prompt = f"You are supporting a user with {session.problem_category.name}. {protocol_text}"
            
            # Check if we should suggest the 7-day plan
            support_msg_count = ChatMessage.objects.filter(session=session, sender="assistant").count()
            if support_msg_count >= 3:
                system_prompt += " The user seems stable. PLEASE suggest starting our 7-day micro-workplan in your response."
        else:
            system_prompt = "Be a supportive listener."

        # 6. Call LLM
        analysis = call_llm(system_prompt, user_content, history=history, json_mode=True)
    
    # 7. Handle Crisis
    if analysis.get("is_crisis"):
        session.current_flow = "crisis"
        session.save()

    # 8. Update State if Category found with high confidence
    detected_cat_name = analysis.get("detected_category")
    confidence = analysis.get("confidence_score", 0)
    
    if detected_cat_name and confidence > 0.8 and session.current_flow == "discovery":
        category = ProblemCategory.objects.filter(name__iexact=detected_cat_name).first()
        if category:
            session.problem_category = category
            session.current_flow = "active_support"
            session.save()

    # 9. Save and Return Assistant Message
    return create_assistant_message(
        session_id,
        content=analysis.get("empathetic_response"),
        suggested_replies=analysis.get("suggested_buttons"),
        metadata={"category": detected_cat_name, "confidence": confidence}
    )
