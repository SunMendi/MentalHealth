import logging
from typing import Any, Dict, Optional
from ..models import ProblemCategory, UserPlan, ClinicalProtocol
from .plans import activate_plan
from .protocols import get_protocol_for_category

logger = logging.getLogger("chat.tools")

# =====================================================================
# 1. TOOL SCHEMAS (The Menu we show to Groq)
# =====================================================================
# Every tool follows the OpenAI / Groq function specification:
# - type: "function"
# - function: { name, description, parameters }

SUPPORTED_CATEGORIES = [
    "General Anxiety",
    "Panic Attacks",
    "Depression",
    "Workplace Stress",
    "Relationship / Family",
    "Grief & Loss"
]

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "activate_support_plan",
            "description": (
                "Activates a personalized 7-day mental health recovery plan for the user in the database. "
                "Call this tool ONLY when you have identified a clear mental health struggle from the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {
                        "type": "string",
                        "description": "The exact mental health category to activate.",
                        "enum": SUPPORTED_CATEGORIES,
                    }
                },
                "required": ["category_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_clinical_protocol",
            "description": (
                "Fetches evidence-based clinical guidelines (CBT, DBT, PST, or Behavioral Activation) "
                "for a specific mental health concern so you can guide the user through a proven exercise."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category_name": {
                        "type": "string",
                        "description": "The category to fetch clinical guidance for.",
                        "enum": SUPPORTED_CATEGORIES,
                    }
                },
                "required": ["category_name"],
            },
        },
    },
]


# =====================================================================
# 2. TOOL EXECUTOR (The Hands that run Python code)
# =====================================================================
def execute_tool(tool_name: str, arguments: Dict[str, Any], user: Any) -> Dict[str, Any]:
    """
    Executes a requested tool function and returns the result to feed back to the AI.
    """
    logger.info("Executing tool: %s with args: %s for user: %s", tool_name, arguments, user)
    
    category_name = arguments.get("category_name")
    
    # -------------------------------------------------------------
    # Tool 1: activate_support_plan
    # -------------------------------------------------------------
    if tool_name == "activate_support_plan":
        if not user or not user.is_authenticated:
            return {
                "status": "error",
                "message": "User is anonymous; 7-day plan cannot be saved to an account."
            }
            
        category = ProblemCategory.objects.filter(name__iexact=category_name).first()
        if not category:
            return {
                "status": "error",
                "message": f"Category '{category_name}' not found in database."
            }
            
        try:
            plan = activate_plan(user, category.id)
            return {
                "status": "success",
                "message": f"Successfully activated 7-day support plan for '{category.name}'.",
                "category": category.name,
                "plan_id": plan.id
            }
        except Exception as exc:
            logger.exception("Failed to activate plan via tool: %s", exc)
            return {
                "status": "error",
                "message": f"Database error activating plan: {str(exc)}"
            }

    # -------------------------------------------------------------
    # Tool 2: fetch_clinical_protocol
    # -------------------------------------------------------------
    elif tool_name == "fetch_clinical_protocol":
        category = ProblemCategory.objects.filter(name__iexact=category_name).first()
        if not category:
            return {
                "status": "error",
                "message": f"Category '{category_name}' not found."
            }
            
        protocol_guide = get_protocol_for_category(category)
        return {
            "status": "success",
            "category": category.name,
            "clinical_protocol": protocol_guide
        }

    # -------------------------------------------------------------
    # Unknown Tool Requested
    # -------------------------------------------------------------
    else:
        return {
            "status": "error",
            "message": f"Unknown tool: '{tool_name}'"
        }
