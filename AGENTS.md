PROJECT: AI Mental Health Support App (Bangladesh + Global)

GOAL:
Build a 24/7 emotional support assistant (NOT a doctor/therapist) that helps users handle:
- panic, anxiety, overthinking, sadness
- relationship stress, loneliness
- suicidal/self-harm thoughts (with safe escalation)

CORE IDEA:
NOT a free chatbot.
It is a GUIDED CHAT SYSTEM.

User talks (text/voice) → system detects:
- intent (problem type)
- risk level
→ routes to correct support flow (CBT, DBT, Panic, Crisis, etc.)

---

CORE SYSTEM FLOW:

handle_user_input(user, input):
1. STT if voice
2. save user message
3. detect risk (hard rules + classifier)
4. detect intent/problem
5. select mode/flow
6. fetch RAG content (if not crisis)
7. generate controlled AI response
8. attach UI options/buttons
9. optional TTS
10. save AI response
11. return response

---

MODES:

- PANIC → breathing + grounding (DBT)
- CBT → thought reframing (overthinking)
- DBT → emotion regulation (high intensity)
- PROBLEM_SOLVING → structured decision making
- GENERAL → supportive chat
- CRISIS → safety mode (no normal chat)

---

CRISIS RULE (CRITICAL):

If user mentions:
- suicide / self-harm / "want to die"
→ STOP normal AI
→ return safety response:
  - call trusted contact
  - show emergency resources
  - short, calm messages only

---

RAG USAGE:

Used for:
- CBT scripts
- DBT exercises
- panic grounding
- relationship advice
- Bangla localized content

NOT used for:
- risk detection
- crisis decisions

---

VOICE:

- STT: Groq Whisper (MVP)
- TTS: Edge TTS (replaceable)
- Flow:
  audio → STT → same chat pipeline → optional TTS

---

FEATURES:

1. Guided Chat
- chat + buttons (options)
- structured conversation, not free AI

2. Mental Health Router
- classify intent, risk, mode

3. Panic Flow
- breathing, grounding, short responses

4. CBT Flow
- thought → evidence → reframe → action

5. DBT Flow
- calm body first → then think

6. Problem Solving
- define problem → options → small action

7. 7-Day Support Plan
- adaptive daily micro-tasks
- user feedback (Better/Same/Worse)

8. Daily Check-in
- mood logging → route to flow

9. Small Acts
- simple positive actions (no pressure)

10. Anonymous Community
- anonymous posts only
- no likes/comments
- moderation required

11. Emotional Tracking (optional MVP+)
- patterns, triggers, summaries

---

UX PRINCIPLES:

- simple
- fast response
- short messages
- always guide next step
- no user confusion
- safety first

---

SAFETY:

- not a doctor disclaimer
- escalate crisis to human/emergency
- trusted contact support

---

MVP PRIORITY (4 DAYS):

Day 1:
- auth + chat session + message API

Day 2:
- chat brain (risk + intent + flow routing)

Day 3:
- RAG integration + full chat flow (text + voice)

Day 4:
- 7-day plan + small acts + anonymous post + final testing

---

BACKEND CORE:

Single orchestrator:
handle_user_input()

Everything depends on this.

---

MENTAL MODEL:

Frontend = UI (chat, buttons, audio)
Backend = brain (decision + safety + logic)

---

END GOAL:

User feels:
"I talked → app understood → gave me right help instantly"

NOT:
"I chatted with random AI"