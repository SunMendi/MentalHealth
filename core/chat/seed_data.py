SEED_DATA = [
    {
        "name": "General Anxiety",
        "description": "Focuses on 'What if' thinking, overthinking, and persistent worry.",
        "protocol": {
            "type": "CBT",
            "content": "Protocol: Cognitive Reframing. 1. Validate the anxiety. 2. Identify the 'Automatic Negative Thought' (ANT). 3. Challenge with evidence. 4. Create a balanced alternative thought."
        },
        "tasks": [
            ("Label the Worry", "Every time you worry, say out loud: 'I am having a thought that...'"),
            ("Schedule Worry Time", "Pick 10 minutes today to worry as much as you want. Outside that time, say 'Not now'."),
            ("Evidence Table", "Write one worry and list 3 reasons why it might NOT come true."),
            ("Control Circle", "List what you can control vs. what you can't about a specific stressor."),
            ("Body Scan", "Notice where you hold tension and release it for 2 minutes."),
            ("The Worst-Case Reality", "If the worst happened, how would you actually cope? Write it down."),
            ("Values Alignment", "Do one small thing today that aligns with your values, regardless of anxiety.")
        ]
    },
    {
        "name": "Panic Attacks",
        "description": "Intense physical fear and physical symptoms.",
        "protocol": {
            "type": "DBT",
            "content": "Protocol: TIPP & Grounding. 1. Immediate physical intervention (Temperature). 2. Sensory grounding (5-4-3-2-1). 3. Paced breathing. Focus on safety and the 'now'."
        },
        "tasks": [
            ("5-4-3-2-1 Grounding", "Name 5 things you see, 4 you feel, 3 hear, 2 smell, 1 taste."),
            ("Cold Water Splash", "Splash cold water on your face to trigger the dive reflex and slow heart rate."),
            ("Box Breathing", "Breathe in for 4, hold for 4, out for 4, hold for 4. Repeat 5 times."),
            ("Muscle Release", "Tense your toes for 5 seconds, then release. Notice the difference."),
            ("Safe Space Visualization", "Describe your safest place in 50 words using all senses."),
            ("Anchor Phrases", "Repeat: 'This is a physical feeling. It is uncomfortable, but I am safe.'"),
            ("Reflection", "Write down one thing that helped you feel grounded today.")
        ]
    },
    {
        "name": "Depression",
        "description": "Low mood, lack of motivation, and sadness.",
        "protocol": {
            "type": "Behavioral Activation",
            "content": "Protocol: Small Acts. 1. Validate the heaviness. 2. Avoid 'thinking'—focus on 'doing'. 3. Break tasks into micro-steps. 4. Celebrate non-zero days."
        },
        "tasks": [
            ("The 2-Minute Rule", "Do one thing you've been avoiding for exactly 2 minutes."),
            ("Sunlight Exposure", "Spend 5 minutes near a window or outside."),
            ("Non-Zero Day", "Clean just one small surface or wash one dish."),
            ("Label one Feeling", "Write down how you feel without trying to change it."),
            ("Reach Out", "Send a simple 'Hi' text to one person you trust."),
            ("Self-Compassion", "Say: 'I am doing my best with the energy I have today.'"),
            ("Movement", "Walk for 5 minutes, even if it's just inside your room.")
        ]
    },
    {
        "name": "Workplace Stress",
        "description": "Burnout, boundary issues, and task overwhelm.",
        "protocol": {
            "type": "PST",
            "content": "Protocol: Problem Solving. 1. Define the specific problem. 2. List all possible options. 3. Evaluate consequences. 4. Pick one small action."
        },
        "tasks": [
            ("The Brain Dump", "List every work task in your head on paper."),
            ("Eisenhower Matrix", "Categorize tasks into Urgent vs. Important."),
            ("Boundary Setting", "Say 'No' or 'Not now' to one non-essential request."),
            ("Transition Ritual", "Do one specific thing to signal the end of the workday."),
            ("Single Tasking", "Work on one thing for 25 minutes with zero distractions."),
            ("Asks for Help", "Identify one thing you can delegate or ask for clarity on."),
            ("Value Check", "Identify why you do this work beyond just the paycheck.")
        ]
    },
    {
        "name": "Relationship / Family",
        "description": "Communication gaps, conflict, and boundary issues.",
        "protocol": {
            "type": "IPT",
            "content": "Protocol: Interpersonal effectiveness. 1. Use 'I' statements. 2. Validate the other person's perspective. 3. Clarify your own needs. 4. Aim for 'Wise Mind'."
        },
        "tasks": [
            ("The 'I' Statement", "Practice saying 'I feel... when... because...' in your head."),
            ("Active Listening", "Listen to someone today without thinking of a rebuttal."),
            ("Self-Validation", "Acknowledge your own feelings in a conflict without blame."),
            ("Soft Startup", "Practice bringing up a small concern gently."),
            ("Boundary Line", "Identify one personal boundary you need to protect."),
            ("Appreciation", "Express one sincere 'Thank you' to a family member or friend."),
            ("Reflection", "What is one thing you can change in your communication?")
        ]
    },
    {
        "name": "Grief & Loss",
        "description": "Processing death, breakups, or major life changes.",
        "protocol": {
            "type": "ACT",
            "content": "Protocol: Acceptance & Values. 1. Create space for the pain. 2. Avoid the 'struggle' against sadness. 3. Identify what still matters. 4. Take value-based action."
        },
        "tasks": [
            ("Memory Box", "Think of one positive memory and hold it for 1 minute."),
            ("Permission to Grieve", "Say: 'It is okay that I am sad today.'"),
            ("Value Identification", "What is one thing that still matters to you right now?"),
            ("Small Legacy", "Do one small act in honor of what was lost."),
            ("Self-Care check", "Ensure you've eaten and hydrated today. Basics matter."),
            ("Write a Letter", "Write a letter to what you lost (don't send it)."),
            ("Quiet Time", "Sit in silence for 5 minutes with your thoughts.")
        ]
    },
    {
        "name": "OCD / Intrusive Thoughts",
        "description": "Repetitive thoughts and the urge to perform compulsions.",
        "protocol": {
            "type": "CBT / ERP",
            "content": "Protocol: Defusion. 1. Label the thought as an 'Intrusive Thought'. 2. Do not argue with it. 3. Delay the compulsion by 1 minute. 4. Refocus on a value-based task."
        },
        "tasks": [
            ("Thought Labeling", "Say: 'I'm having the obsession that...'"),
            ("The 5-Minute Delay", "Delay a checking or cleaning behavior for 5 minutes."),
            ("Externalizing", "Give your OCD a silly name and talk back to it."),
            ("uncertainty Acceptance", "Repeat: 'Maybe, maybe not. I can live with the doubt.'"),
            ("Focus Shift", "Engage in a complex task (like a puzzle) for 10 minutes."),
            ("No Reassurance", "Try not to ask anyone 'is this okay?' for 3 hours."),
            ("Victory Log", "Write down one time you resisted a compulsion today.")
        ]
    },
    {
        "name": "Anger / Irritability",
        "description": "Quick temper, frustration, and emotional volatility.",
        "protocol": {
            "type": "DBT",
            "content": "Protocol: Emotion Regulation. 1. Notice the physical 'heat' of anger. 2. Use the 'Stop' skill. 3. Opposite Action (act kind if feeling mean). 4. Check the facts."
        },
        "tasks": [
            ("Identify the Trigger", "What exactly made you feel hot/angry? Write it down."),
            ("The 10-Second Pause", "Wait 10 seconds before responding when frustrated."),
            ("Physical Release", "Squeeze a stress ball or use intense exercise for 2 minutes."),
            ("Opposite Action", "Do one small kind thing for someone you're annoyed with."),
            ("The 'Why' behind Anger", "Is there sadness or fear under the anger? Label it."),
            ("Cool Down", "Use a cold compress on your neck when you feel 'heated'."),
            ("Gratitude", "List 3 things that didn't go wrong today.")
        ]
    },
    {
        "name": "Social Anxiety",
        "description": "Fear of judgment, embarrassment, and social avoidance.",
        "protocol": {
            "type": "CBT",
            "content": "Protocol: Exposure & Testing. 1. Identify the 'Social Catastrophe'. 2. Rate the probability (0-100%). 3. Small social 'experiment'. 4. De-brief."
        },
        "tasks": [
            ("Small Greeting", "Say 'Hello' or 'Good morning' to one person."),
            ("Eye Contact", "Try to hold eye contact for 2 seconds with a cashier."),
            ("The Spotlight Fallacy", "Remind yourself: 'People aren't looking at me as much as I think.'"),
            ("Ask a Question", "Ask one person a simple question (e.g., 'What time is it?')."),
            ("Public Space", "Sit in a cafe or park for 10 minutes without a phone."),
            ("Small Mistake", "Purposely drop a pen and see if anyone laughs (they won't)."),
            ("Positive Reflection", "What is one thing that went okay in a social interaction today?")
        ]
    }
]
