import os
from state import StudyPlannerState
from agent import run_agent, get_groq_client

# Define Mock classes to simulate Groq API without internet or API key
class MockMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockCompletion:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

class MockCompletions:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0
        
    def create(self, **kwargs):
        if self.call_count < len(self.responses):
            res = MockCompletion(self.responses[self.call_count])
            self.call_count += 1
            return res
        else:
            return MockCompletion(
                '{"thought": "Default complete", "action": "final_answer", "message": "Planning complete."}'
            )

class MockChat:
    def __init__(self, responses):
        self.completions = MockCompletions(responses)

class MockGroqClient:
    def __init__(self, responses):
        self.chat = MockChat(responses)


# Realistic JSON response sequence to simulate the Llama model on Groq
MOCK_RESPONSES = [
    # Step 1: LLM decides to add the Physics Quiz
    '''{
      "thought": "I see three tasks in the goal. I should add the Physics Quiz first since it is due earliest on 2026-08-12.",
      "action": "call_tool",
      "tool_name": "add_task",
      "tool_args": {"name": "Physics Quiz", "due": "2026-08-12"}
    }''',
    
    # Step 2: LLM decides to add the History Homework
    '''{
      "thought": "Now I will add the History Homework, which is due on 2026-08-13.",
      "action": "call_tool",
      "tool_name": "add_task",
      "tool_args": {"name": "History Homework", "due": "2026-08-13"}
    }''',
    
    # Step 3: LLM decides to add the Math Exam
    '''{
      "thought": "Next, I need to add the Math Exam, due on 2026-08-14.",
      "action": "call_tool",
      "tool_name": "add_task",
      "tool_args": {"name": "Math Exam", "due": "2026-08-14"}
    }''',
    
    # Step 4: LLM decides to build the schedule
    '''{
      "thought": "All tasks are now stored. I will run build_schedule to calculate the optimal daily study blocks.",
      "action": "call_tool",
      "tool_name": "build_schedule",
      "tool_args": {}
    }''',
    
    # Step 5: LLM decides to return the final answer
    '''{
      "thought": "The schedule has been successfully built. I will now present the finalized study plan to the user.",
      "action": "final_answer",
      "message": "Here is your study plan starting 2026-08-11:\\n\\n- **2026-08-11 (Day 1)**:\\n  * Physics Quiz (2.0 hours) - review before tomorrow's quiz\\n  * History Homework (2.0 hours) - write homework due 2026-08-13\\n  *Total: 4.0 hours*\\n\\n- **2026-08-12 (Day 2)**:\\n  * Math Exam (4.0 hours) - study block 1 for exam on 2026-08-14\\n  *Total: 4.0 hours*\\n\\n- **2026-08-13 (Day 3)**:\\n  * Math Exam (2.0 hours) - study block 2 / final review\\n  *Total: 2.0 hours*\\n\\nAll study blocks have been allocated before the deadlines, respecting your daily limit of 4 hours."
    }'''
]


def test_agent_run():
    print("=" * 60)
    print("      STUDY PLANNER AGENT RUN (GROQ API)")
    print("=" * 60)
    
    # Initialize State starting on 2026-08-11
    state = StudyPlannerState(start_date="2026-08-11")
    
    goal = (
        "I need to prepare for my upcoming assessments: a Math Exam due on 2026-08-14, "
        "History Homework due on 2026-08-13, and Physics Quiz due on 2026-08-12. "
        "Please schedule study blocks for them."
    )
    
    print(f"Goal: {goal}\n")
    
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        print("[System] GROQ_API_KEY detected. Running with LIVE Groq API...\n")
        try:
            client = get_groq_client()
            final_ans, history = run_agent(goal, state, client)
        except Exception as e:
            print(f"[System] Live API execution failed: {e}. Falling back to simulation.")
            client = MockGroqClient(MOCK_RESPONSES)
            final_ans, history = run_agent(goal, state, client)
    else:
        print("[System] No GROQ_API_KEY found in environment.")
        print("[System] Running in SIMULATION MODE with Mock Groq Client...\n")
        client = MockGroqClient(MOCK_RESPONSES)
        final_ans, history = run_agent(goal, state, client)
        
    print("=" * 60)
    print("      AGENT EXECUTION TRACE (MEMORY)")
    print("=" * 60)
    for step in history:
        print(f"Step {step['step']}:")
        print(f"  Thought: {step['thought']}")
        print(f"  Action: {step['action']}")
        print(f"  Observation: {step['observation']}")
        print("-" * 60)

if __name__ == "__main__":
    test_agent_run()
