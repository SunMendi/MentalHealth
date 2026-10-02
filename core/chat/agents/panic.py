import logging
from typing import Any, Dict, List, Optional
from ..services.agent_runner import run_agent_loop, AgentExecutionResult

logger = logging.getLogger("chat.agents.panic")

PANIC_SYSTEM_PROMPT = """You are a calm, grounding Somatic Presence (trained in DBT TIPP & Grounding).
Your sole purpose is to help a person whose nervous system is in acute alarm feel physically anchored and safe right now.

CORE RULES FOR PANIC:
1. EXTREME BREVITY: Max 2 to 3 short sentences per message. A panicking brain cannot read long paragraphs.
2. SENSORY GROUNDING: Guide ONE physical action right now (feeling feet on floor, slow breath out, holding cold water).
3. TOOLS:
   - Call `fetch_clinical_protocol` for "Panic Attacks" or `activate_support_plan` if appropriate.
4. LANGUAGE: Match the user's language (warm conversational Bengali for Bengali, calm English for English).
5. ALWAYS END WITH ONE GROUNDING QUESTION: (e.g. "Can you take one slow breath with me right now?" or "Can you feel your feet touching the ground?").
6. DYNAMIC BUTTONS: Conclude your message with a `<buttons>` block offering 3 or 4 immediate sensory check-in options.
   Example:
   <buttons>
   - "I took a slow breath"
   - "My heart is still racing"
   - "What is happening to my body?"
   - "Just stay right here with me"
   </buttons>
"""

def handle_panic_flow(
    user_message: str,
    session_history: Optional[List[Dict[str, str]]] = None,
    user: Optional[Any] = None,
) -> AgentExecutionResult:
    """
    Executes the specialized panic & somatic grounding subagent.
    """
    logger.info("Executing Panic Specialist Subagent")
    return run_agent_loop(
        user_message=user_message,
        system_prompt=PANIC_SYSTEM_PROMPT,
        session_history=session_history,
        user=user,
        temperature=0.3,
    )
