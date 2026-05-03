import os
import json
import logging
import google.generativeai as genai
from typing import Dict, Any, List, Optional

logger = logging.getLogger("chat.llm")

# Initialize Gemini Client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.error("CRITICAL: GEMINI_API_KEY is missing!")

def call_gemini(system_prompt: str, user_message: str, audio_path: Optional[str] = None, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Calls Google Gemini 1.5 Flash (Most stable for Free Tier).
    """
    try:
        # Switching to 1.5-flash for better quota stability in 2026
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_prompt
        )

        prompt_parts = []
        
        # 1. Handle Audio (Multimodal)
        if audio_path and os.path.exists(audio_path):
            try:
                with open(audio_path, "rb") as f:
                    audio_data = f.read()
                    mime_type = "audio/wav"
                    if audio_path.endswith(".mp3"): mime_type = "audio/mpeg"
                    elif audio_path.endswith(".webm"): mime_type = "audio/webm"
                    
                    prompt_parts.append({
                        "mime_type": mime_type,
                        "data": audio_data
                    })
                logger.info("Audio attached to Gemini request | path=%s", audio_path)
            except Exception as e:
                logger.error("Failed to read audio file for Gemini: %s", e)

        # 2. Handle Text & History
        context_msg = ""
        if history:
            context_msg = "Context:\n" + "\n".join([f"{m['role']}: {m['content']}" for m in history]) + "\n"
        
        prompt_parts.append(f"{context_msg}User Message: {user_message or 'Please respond to the audio provided.'}")

        # 3. Request
        generation_config = {
            "temperature": 0.7,
            "response_mime_type": "application/json",
        }

        response = model.generate_content(
            prompt_parts,
            generation_config=generation_config
        )

        if not response or not response.text:
            raise ValueError("Gemini returned an empty response")

        return json.loads(response.text)

    except Exception as e:
        # Log the REAL error so we can see it in Railway
        logger.error("Gemini API Error Detail: %s", str(e))
        
        # If it's a quota error, tell the user politely
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg:
            return {
                "empathetic_response": "I'm receiving too many messages right now. Please wait a few seconds and try again. (Bengali: আমি এই মুহূর্তে অনেক বার্তা পাচ্ছি। দয়া করে কয়েক সেকেন্ড অপেক্ষা করুন।)",
                "detected_category": None,
                "confidence_score": 0.0,
                "suggested_buttons": ["Wait and retry"],
                "is_crisis": False
            }
            
        return {
            "empathetic_response": "I'm having a technical connection issue. Please check your internet or try again. (Bengali: আমার সংযোগে কিছুটা সমস্যা হচ্ছে। দয়া করে আবার চেষ্টা করুন।)",
            "detected_category": None,
            "confidence_score": 0.0,
            "suggested_buttons": ["Try again"],
            "is_crisis": False
        }
