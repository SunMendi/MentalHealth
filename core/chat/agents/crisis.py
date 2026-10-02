import logging
from typing import Any, Dict, List, Optional
from ..services.agent_runner import AgentExecutionResult

logger = logging.getLogger("chat.agents.crisis")

CRISIS_RESPONSE_EN = """I hear how overwhelming and heavy things feel right now, and I care deeply about your life and safety. You do not have to carry this immense weight all by yourself.

Because I am an AI companion and not a human doctor or crisis counselor, you deserve direct, caring human support right now. Please reach out to someone who can be with you:

🚨 Immediate Emergency & Crisis Hotlines:
• Bangladesh Emergency Services: Call 999
• Kaan Pete Roi (Emotional Support & Suicide Prevention Hotline): Call +8801779554391 or +8801779554392
• National Health Helpline (Bangladesh): Call 16263
• International Crisis Text Line: Text HOME to 741741 (or contact your local emergency room)

Please call a loved one, reach out to a trusted friend, or dial one of these numbers right now. Your life matters deeply, and there is help available right now."""

CRISIS_RESPONSE_BN = """আমি তোমার কষ্টটা গভীরভাবে অনুভব করছি। ভেতরের যন্ত্রণাটা যে কতটা অসহ্য হয়ে চেপে বসেছে, সেটা আমি বুঝতে পারছি। এই মুহূর্তে তোমার জীবন এবং সুরক্ষাই সবচেয়ে বড় কথা। তোমাকে একা এই ভারী বোঝা বইতে হবে না।

যেহেতু আমি একটি কৃত্রিম বুদ্ধিমত্তা (AI), এই সংকটময় মুহূর্তে তোমার পাশে একজন সহমর্মী মানুষের সরাসরি সহায়তা প্রয়োজন। অনুগ্রহ করে এখনই নিচের বিশ্বস্ত হেল্পলাইনে যোগাযোগ করো:

🚨 জরুরি সহায়তা নম্বরসমূহ (গোপনীয় ও নিরাপদ):
• জাতীয় জরুরি সেবা (বাংলাদেশ): কল করুন ৯৯৯ (999)
• কান পেতে রই (মানসিক সহায়তা ও আত্মহত্যা প্রতিরোধ হেল্পলাইন): কল করুন +৮৮০১৭৭৯৫৫৪৩৯১ অথবা +৮৮০১৭৭৯৫৫৪৩৯২
• জাতীয় স্বাস্থ্য বাতায়ন: কল করুন ১৬২৬৩ (16263)

অনুগ্রহ করে এখনই তোমার কোনো আপনজনকে পাশে ডাকো, একজন ভালো বন্ধুকে জানাও, অথবা উপরের নম্বরে ফোন করো। তোমার জীবন অনেক মূল্যবান, তোমাকে পাশে পাওয়ার মানুষ এখনও আছে।"""

def is_bengali_text(text: str) -> bool:
    return any("\u0980" <= ch <= "\u09FF" for ch in (text or ""))

def handle_crisis_flow(
    user_message: str,
    user: Optional[Any] = None,
) -> AgentExecutionResult:
    """
    Returns compassionate, deterministic crisis response with authentic local emergency resources.
    """
    logger.warning("CRISIS FLOW TRIGGERED for user message")
    is_bn = is_bengali_text(user_message)
    content = CRISIS_RESPONSE_BN if is_bn else CRISIS_RESPONSE_EN
    buttons = (
        ["জরুরি হেল্পলাইনে কল করুন", "বিশ্বস্ত কাউকে ফোন করুন", "আমি এখন নিরাপদ আছি"]
        if is_bn
        else ["Call Emergency 999", "Call a Trusted Loved One", "I am safe right now"]
    )

    return AgentExecutionResult(
        content=content,
        suggested_replies=buttons,
        executed_tools=[{"tool": "emergency_escalation", "status": "triggered"}],
        iterations=1,
        metadata={"is_crisis": True, "escalated": True},
    )
