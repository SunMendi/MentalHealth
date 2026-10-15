import json
import logging
import re
from typing import Any, Dict, List, Optional
from django.contrib.auth import get_user_model

from .llm import call_agent_llm, client, GROQ_CHAT_MODEL
from .tools import AGENT_TOOLS, execute_tool

logger = logging.getLogger(__name__)

User = get_user_model()


class AgentExecutionResult:
    """
    Structured outcome of an autonomous agent run.
    """
    def __init__(
        self,
        content: str,
        suggested_replies: List[str],
        executed_tools: List[Dict[str, Any]],
        iterations: int,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.content = content
        self.suggested_replies = suggested_replies
        self.executed_tools = executed_tools
        self.iterations = iterations
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "suggested_replies": self.suggested_replies,
            "executed_tools": self.executed_tools,
            "iterations": self.iterations,
            "metadata": self.metadata,
        }


def _fallback_emotional_buttons(text: str) -> List[str]:
    """
    Fallback buttons that represent authentic internal emotional voices.
    """
    lower = (text or "").lower()
    
    # Bengali fallback
    if any("\u0980" <= ch <= "\u09FF" for ch in text):
        if "শ্বাস" in lower or "শরীর" in lower:
            return ["শ্বাস নিতে সাহায্য করো", "আমি একটু শান্ত বোধ করছি", "এখনও শরীর কাঁপছে", "পাশে থাকো"]
        if "চিন্তা" in lower or "ভয়" in lower:
            return ["চিন্তাটা গুছিয়ে বলতে চাই", "সবকিছু গুলিয়ে যাচ্ছে", "আমাকে সান্ত্বনা দাও", "এখন কী করব?"]
        return ["আরও কথা বলতে চাই", "আমার পাশে থাকো", "একটা ছোট কাজ বলো", "খুব একা লাগছে"]

    # English Panic / Somatic context
    if "breathe" in lower or "5-4-3-2-1" in lower or "ground" in lower or "feet" in lower:
        return ["I did this step", "Help me breathe slower", "I still feel shaky", "Stay with me"]
        
    # English CBT / Overthinking context
    if "thought" in lower or "evidence" in lower or "worry" in lower or "career" in lower:
        return ["The pressure is too much", "I feel like a failure", "Help me organize my thoughts", "I just need to vent"]
        
    # English Depression / Low Energy context
    if "heavy" in lower or "tiny" in lower or "sad" in lower or "empty" in lower:
        return ["I feel completely drained", "I just want someone to listen", "Give me one tiny 2-min step", "Don't leave me alone"]
        
    # Default internal voice options
    return ["Tell you more about it", "I don't know where to start", "Help me feel calmer", "What should I do?"]


def _parse_dynamic_buttons_and_clean_text(raw_text: str) -> tuple[str, List[str]]:
    """
    Extracts dynamic buttons enclosed in <buttons>...</buttons> tags and strips
    them from the user-facing message. If no tags exist, uses emotional fallbacks.
    """
    buttons: List[str] = []
    clean_text = raw_text or ""
    
    match = re.search(r"<buttons>(.*?)</buttons>", clean_text, re.DOTALL | re.IGNORECASE)
    if match:
        block = match.group(1).strip()
        clean_text = re.sub(r"<buttons>.*?</buttons>", "", clean_text, flags=re.DOTALL | re.IGNORECASE).strip()
        for line in block.split("\n"):
            line = line.strip().strip("-*•>").strip()
            line = re.sub(r'^["\']|["\']$', '', line).strip()
            if line and len(line) <= 45:
                buttons.append(line)

    if not buttons:
        buttons = _fallback_emotional_buttons(clean_text)

    return clean_text, buttons[:4]


def run_agent_loop(
    user_message: str,
    system_prompt: str,
    session_history: Optional[List[Dict[str, str]]] = None,
    user: Optional[Any] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_iterations: int = 4,
    temperature: float = 0.6,
) -> AgentExecutionResult:
    """
    The Core Autonomous Agent Decision Loop (ReAct: Reason -> Act -> Observe).
    
    Continuously converses with the LLM and executes tools until the LLM
    decides it has all needed information and delivers its final message.
    """
    active_tools = tools if tools is not None else AGENT_TOOLS
    executed_tools: List[Dict[str, Any]] = []

    # 1. Prepare initial conversation context
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]

    for item in session_history or []:
        role = item.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": item.get("content", "")})

    # Add the current user message
    messages.append({"role": "user", "content": user_message})

    iteration = 0
    final_content = ""

    # =====================================================================
    # THE AUTONOMOUS DECISION LOOP
    # =====================================================================
    while iteration < max_iterations:
        iteration += 1
        logger.info("Agent loop iteration %d/%d | messages=%d", iteration, max_iterations, len(messages))

        # Ask the AI: "Here is the state. What is your next move?"
        choice = call_agent_llm(
            messages=messages,
            tools=active_tools,
            temperature=temperature,
        )

        # -----------------------------------------------------------------
        # CASE A: AI decides it needs to execute TOOLS
        # -----------------------------------------------------------------
        if choice.tool_calls:
            # 1. In standard agent protocols, we MUST append the assistant's
            # tool-call request to conversation history first!
            assistant_tool_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.tool_calls
                ],
            }
            messages.append(assistant_tool_msg)

            # 2. Execute each tool requested by the AI
            for tool_call in choice.tool_calls:
                tool_name = tool_call.function.name
                raw_args = tool_call.function.arguments
                
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception as parse_err:
                    logger.error("Failed to parse tool arguments: %s | raw=%s", parse_err, raw_args)
                    args = {}

                logger.info("Agent executing tool: %s with args: %s", tool_name, args)
                tool_output = execute_tool(tool_name, args, user=user)

                # Track for final metadata
                executed_tools.append({
                    "tool": tool_name,
                    "arguments": args,
                    "result": tool_output,
                })

                # 3. Feed the tool observation back to the AI
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(tool_output),
                })

            # The while loop will now repeat! The AI will observe the tool results.
            continue

        # -----------------------------------------------------------------
        # CASE B: AI is DONE and delivered its final response
        # -----------------------------------------------------------------
        final_content = choice.content or ""
        logger.info("Agent finished thinking. Generated response preview: %s", final_content[:100])
        break

    # If the circuit breaker was reached without text
    if not final_content:
        final_content = (
            "I'm here with you. Let's take a slow breath together. "
            "How does your body feel right now?"
        )

    # Clean dynamic buttons and extract interactive replies
    clean_content, buttons = _parse_dynamic_buttons_and_clean_text(final_content)

    return AgentExecutionResult(
        content=clean_content,
        suggested_replies=buttons,
        executed_tools=executed_tools,
        iterations=iteration,
        metadata={
            "tool_count": len(executed_tools),
            "tools_called": [t["tool"] for t in executed_tools],
        },
    )


class StreamingButtonFilter:
    """
    Filters out <buttons>...</buttons> tags from the streaming token stream
    and extracts structured options for UI chips.
    """
    def __init__(self):
        self.buffer = ""
        self.in_buttons = False
        self.buttons_text = ""

    def process(self, chunk: str) -> str:
        out = []
        for ch in chunk:
            if not self.in_buttons:
                self.buffer += ch
                lower = self.buffer.lower()
                if "<buttons>" in lower:
                    idx = lower.index("<buttons>")
                    out.append(self.buffer[:idx])
                    self.in_buttons = True
                    self.buttons_text += self.buffer[idx + len("<buttons>"):]
                    self.buffer = ""
                elif not "<buttons>".startswith(lower):
                    out.append(self.buffer)
                    self.buffer = ""
            else:
                self.buttons_text += ch
        return "".join(out)

    def finalize(self) -> tuple[str, List[str]]:
        out = self.buffer if not self.in_buttons else ""
        buttons_raw = (
            self.buttons_text.replace("</buttons>", "")
            .replace("</BUTTONS>", "")
            .strip()
        )
        buttons = [
            line.strip().strip("-*•>").strip("\"' ")
            for line in buttons_raw.split("\n")
            if line.strip().strip("-*•>").strip("\"' ")
        ]
        return out, [b for b in buttons if len(b) <= 45][:4]


def run_agent_loop_stream(
    user_message: str,
    system_prompt: str,
    session_history: Optional[List[Dict[str, str]]] = None,
    user: Optional[Any] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_iterations: int = 4,
    temperature: float = 0.6,
):
    """
    Autonomous Agent Decision Loop with real-time SSE token streaming.
    Yields:
      - {"type": "token", "content": clean_chunk}
      - {"type": "agent_finished", "buttons": [...], "executed_tools": [...], "iterations": int}
    """
    if not client:
        raise RuntimeError("Groq client is not initialized.")

    active_tools = tools if tools is not None else AGENT_TOOLS
    executed_tools: List[Dict[str, Any]] = []

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]

    for item in session_history or []:
        role = item.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": item.get("content", "")})

    messages.append({"role": "user", "content": user_message})

    button_filter = StreamingButtonFilter()
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        logger.info("Agent streaming loop iteration %d/%d | messages=%d", iteration, max_iterations, len(messages))

        tool_calls_dict: Dict[int, Dict[str, str]] = {}
        has_content = False

        stream = client.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=messages,
            tools=active_tools,
            temperature=temperature,
            stream=True,
        )

        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta

            # Accumulate streaming tool calls if model wants to call functions
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function and tc.function.name else "",
                            "arguments": tc.function.arguments or "",
                        }
                    else:
                        if tc.id:
                            tool_calls_dict[idx]["id"] += tc.id
                        if tc.function and tc.function.name:
                            tool_calls_dict[idx]["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_dict[idx]["arguments"] += tc.function.arguments

            # Stream text tokens directly to user
            if delta.content:
                has_content = True
                clean_chunk = button_filter.process(delta.content)
                if clean_chunk:
                    yield {"type": "token", "content": clean_chunk}

        # If tools were invoked in this turn
        if tool_calls_dict:
            assistant_tool_msg = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc_info["id"] or f"call_{idx}",
                        "type": "function",
                        "function": {
                            "name": tc_info["name"],
                            "arguments": tc_info["arguments"],
                        },
                    }
                    for idx, tc_info in tool_calls_dict.items()
                ],
            }
            messages.append(assistant_tool_msg)

            for idx, tc_info in tool_calls_dict.items():
                tool_name = tc_info["name"]
                try:
                    args = json.loads(tc_info["arguments"]) if tc_info["arguments"] else {}
                except Exception:
                    args = {}

                tool_output = execute_tool(tool_name, args, user=user)
                executed_tools.append({
                    "tool": tool_name,
                    "arguments": args,
                    "result": tool_output,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_info["id"] or f"call_{idx}",
                    "name": tool_name,
                    "content": json.dumps(tool_output),
                })
            # Loop again to generate final response incorporating tool observation
            continue

        if has_content:
            break

    final_out, buttons = button_filter.finalize()
    if final_out:
        yield {"type": "token", "content": final_out}

    yield {
        "type": "agent_finished",
        "buttons": buttons,
        "executed_tools": executed_tools,
        "iterations": iteration,
    }

