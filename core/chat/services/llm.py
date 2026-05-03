import os
import json
import logging
import google.generativeai as genai
from typing import Dict, Any, List, Optional

logger = logging.getLogger("chat.llm")

# Initialize Gemini Client
# Engineers: We use the Google Generative AI SDK for robust multimodal support.
# Documentation: https://ai.google.dev/gemini-api/docs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY is missing from environment variables.")

def call_gemini(system_prompt: str, user_message: str, audio_path: Optional[str] = None, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Calls Google Gemini 2.0 Flash with optional audio support.
    
    This function is designed to be:
    1. Multimodal: Can process audio directly for native-level Bengali recognition.
    2. Reliable: Includes structured JSON parsing and graceful error handling.
    3. Managable: Follows standard Python typing and clean logging.
    """
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=system_prompt
        )

        # Build the prompt parts
        prompt_parts = []
        
        # Add audio if provided (This is the key for perfect Bengali STT)
        if audio_path and os.path.exists(audio_path):
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
                # Determine mime type based on extension (simple way)
                mime_type = "audio/wav"
                if audio_path.endswith(".mp3"): mime_type = "audio/mpeg"
                elif audio_path.endswith(".webm"): mime_type = "audio/webm"
                
                prompt_parts.append({
                    "mime_type": mime_type,
                    "data": audio_bytes
                })
        
        # Add text history context
        if history:
            # Engineers: Gemini works best when history is provided as clear conversational turns.
            context_str = "Conversation History:\n"
            for msg in history:
                context_str += f"{msg['role'].capitalize()}: {msg['content']}\n"
            prompt_parts.append(f"{context_str}\nUser's current message: {user_message}")
        else:
            prompt_parts.append(user_message)

        # Configure JSON response format
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json",
        }

        response = model.generate_content(
            prompt_parts,
            generation_config=generation_config
        )

        # Parse and return JSON
        if not response or not response.text:
            raise ValueError("Empty response from Gemini API")

        return json.loads(response.text)

    except Exception as e:
        logger.exception("Gemini API call failed: %s", e)
        # Professional fallback response to prevent frontend crashes
        return {
            "empathetic_response": "I'm here for you, but I'm having a little trouble with my connection. Could you repeat that? (Bengali: আমি আপনার সাথে আছি, কিন্তু সংযোগে কিছুটা সমস্যা হচ্ছে।)",
            "detected_category": None,
            "confidence_score": 0.0,
            "suggested_buttons": ["Try again"],
            "is_crisis": False
        }
