import os
import json
from groq import Groq

# Initialize client - Groq SDK handles the base URL correctly by default.
# We explicitly set base_url to None to avoid environment variable interference.
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=None 
)

def call_llm(system_prompt, user_message, history=None, json_mode=True):
    """
    Calls the Groq API using Llama 3 models.
    """
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    
    # Add history if provided (not implemented in brain.py yet, but ready)
    if history:
        messages.extend(history)
        
    messages.append({"role": "user", "content": user_message})

    # Add mandatory JSON formatting instruction to system prompt if in json_mode
    if json_mode:
        json_instruction = """
        IMPORTANT: Your entire response must be a single valid JSON object with these keys:
        {
          "empathetic_response": "string (The text the user will see)",
          "detected_category": "string or null (One of: Anxiety, Panic, Stress, Depression, Grief, Relationship)",
          "confidence_score": "float (0.0 to 1.0)",
          "suggested_buttons": ["string", "string"],
          "is_crisis": "boolean"
        }
        """
        messages[0]["content"] += json_instruction

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0.7,
            max_tokens=1024,
        )
        
        response_content = completion.choices[0].message.content
        
        if json_mode:
            return json.loads(response_content)
        return response_content

    except Exception as e:
        print(f"Error calling Groq: {e}")
        # Fallback safe response
        return {
            "empathetic_response": "I'm here for you, but I'm having a little trouble connecting right now. Can you tell me more about how you're feeling?",
            "detected_category": None,
            "confidence_score": 0.0,
            "suggested_buttons": ["Try again"],
            "is_crisis": False
        }
