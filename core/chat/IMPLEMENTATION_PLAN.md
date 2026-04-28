# Backend Implementation Strategy: AI Mental Health Support

## Phase 1: Knowledge Architecture (The Database)
We must move clinical knowledge out of the LLM prompts and into a structured database.

### 1.1 Clinical Data Models
*   **`ProblemCategory`**: Stores the types of issues (e.g., Social Anxiety, Workplace Stress, Grief).
*   **`ClinicalProtocol`**: Stores the "Solution." Linked to a category. Contains the specific steps for CBT, DBT, or Problem Solving.
*   **`MicroAction`**: A library of small, achievable tasks (7 tasks per category) for the 7-day plan.

### 1.2 Conversation State Models
*   **`ChatSession`**: Tracks `current_flow` (`discovery`, `active_support`, `crisis`) and `problem_category`.
*   **`ChatMessage`**: Tracks `suggested_replies` (buttons) and `metadata` (which protocol was used).

---

## Phase 2: The Mental Health Router (The Brain)
The core logic that decides "What is the user's problem?" and "What do they need right now?"

### 2.1 The Orchestrator Service (`brain.py`)
1.  **Risk Detection:** First pass using keywords + LLM to check for crisis.
2.  **Intent Classification:** LLM analyzes the message to detect the `ProblemCategory`.
3.  **Flow Routing:**
    *   If `category` is unknown → Stay in `discovery` flow.
    *   If `category` is found → Move to `active_support` flow.

### 2.2 Structured LLM Output
Use **JSON mode** for the LLM. Every analysis should return:
```json
{
  "empathetic_response": "I hear how heavy that feels...",
  "detected_category": "Anxiety",
  "confidence_score": 0.9,
  "suggested_buttons": ["Tell me more", "I want a tool"],
  "is_crisis": false
}
```

---

## Phase 3: Guided Chat Implementation (Intake Phase)
### 3.1 The "Intake" System Prompt
Instruction to the LLM: *"You are a compassionate clinical intake assistant. Your goal is to validate the user's pain and ask ONE clarifying question to determine if their issue is [List of Categories]. Use non-judgmental, open-ended language."*

### 3.2 State Management
*   **Session Start:** `current_flow = discovery`.
*   **The Loop:** LLM asks → User responds → Router analyzes.
*   **Transition:** Once `confidence_score > 0.8`, update DB session and fetch the **ClinicalProtocol**.

---

## Phase 4: Hybrid RAG System (Retrieval)
1.  Identify `ProblemCategory`.
2.  Query `ClinicalProtocol.objects.get(category=category)`.
3.  Inject the protocol content into the **System Prompt** for the next turn.

---

## Phase 5: 7-Day Micro-Workplan Engine
### 5.1 Plan Models
*   **`UserPlan`**: Tracks active plans for users.
*   **`PlanProgress`**: Tracks Day 1 to Day 7 completion status.

### 5.2 Plan Activation
Trigger a "Plan Proposal" once `active_support` has reached a stable threshold (e.g., 5-10 messages).

---

## Phase 6: Safety & Crisis Guardrails
### 6.1 Deterministic Crisis Detection
*   **Hard Rules:** Regex/Keyword matching for high-risk terms.
*   **The Safety Trigger:** If triggered, `current_flow` immediately becomes `crisis`, bypassing the LLM.

---

## Project Structure (Target)
```text
core/chat/
├── models.py        # Categories, Protocols, Sessions, Messages, Plans
├── services/
│   ├── brain.py     # The Orchestrator (Router)
│   ├── llm.py       # Groq/OpenAI API wrappers
│   ├── protocols.py # RAG & Retrieval logic
│   └── safety.py    # Crisis & Risk detection
├── views.py         # API Endpoints
└── serializers.py   # JSON conversion
```
