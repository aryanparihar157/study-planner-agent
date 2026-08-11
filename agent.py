import os
import json
import traceback
from google import genai
from google.genai import types
from state import StudyPlannerState
import tools

# A mapping of tool names to their actual Python functions
TOOL_REGISTRY = {
    "add_task": tools.add_task,
    "build_schedule": tools.build_schedule
}

def get_genai_client(api_key: str = None) -> genai.Client:
    """
    Initializes and returns a Google GenAI Client.
    Will check for standard environmental variable if API key is not supplied.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY not found. Please set the environment variable "
            "or pass it directly to get_genai_client(api_key='...')."
        )
    return genai.Client(api_key=key)


def get_system_instruction() -> str:
    """Returns the system prompt instructing the agent on its role and output format."""
    return """You are a Study Planner Agent (Topic T24). Your goal is to plan study blocks around real deadlines.
You must run a plan-act loop, using tools to store tasks and build a schedule, rather than just answering directly.

You have access to the following tools:
1. `add_task(name: str, due: str)`
   - Stores a study task with its due date (YYYY-MM-DD format).
   - Use this to store all tasks the user mentions.
2. `build_schedule()`
   - Builds a chronological study schedule from all stored tasks.
   - Fits study blocks before each due date, ordering tasks by deadline.
   - Returns daily study allocations and flags any schedule conflicts.

At each step, you must output a single JSON object. You have three possible actions:

1. Call a tool:
   {
     "thought": "Brief explanation of why you are calling this tool",
     "action": "call_tool",
     "tool_name": "add_task",
     "tool_args": {"name": "Task Name", "due": "YYYY-MM-DD"}
   }
   OR
   {
     "thought": "Brief explanation of why you are building the schedule",
     "action": "call_tool",
     "tool_name": "build_schedule",
     "tool_args": {}
   }

2. Ask the user for clarification (if you are missing crucial information like a deadline):
   {
     "thought": "Brief explanation of what information is missing",
     "action": "ask_user",
     "message": "Clarification question to show the user"
   }

3. Provide the final study plan / answer:
   {
     "thought": "Brief explanation of why the plan is complete",
     "action": "final_answer",
     "message": "A detailed, friendly summary of the final schedule, study blocks, and any conflict warnings."
   }

Strict Rules:
- You must output VALID JSON. No extra text, markdown formatting blocks around JSON, or explanation outside JSON.
- If the user specifies tasks/deadlines, you must call `add_task` for each before calling `build_schedule`.
- You must call `build_schedule` to generate the schedule structure before providing the `final_answer`.
- Be agentic: Analyze deadlines, ensure study blocks are scheduled BEFORE the task's due date, and report any conflicts or capacity warnings.
"""


def format_agent_prompt(goal: str, state: StudyPlannerState) -> str:
    """Formats the current state, task list, and step history into a prompt for the LLM."""
    state_dict = state.to_dict()
    
    # We construct a context showing current tasks, current start date, and max study hours
    prompt = f"""### Current Start Date: {state.start_date}
### Daily Study Limit: {state.max_study_hours_per_day} hours/day

### User Goal:
"{goal}"

### Currently Stored Tasks:
{json.dumps(state_dict["tasks"], indent=2)}

### Current Execution Trace (Memory):
"""
    if not state.history:
        prompt += "No steps taken yet.\n"
    else:
        for step in state.history:
            prompt += f"Step {step['step']}:\n"
            prompt += f"  - Action Taken: {json.dumps(step['action'])}\n"
            prompt += f"  - Observation: {step['observation']}\n\n"
            
    prompt += "\nRespond with your next action in the required JSON format."
    return prompt


def run_agent(goal: str, state: StudyPlannerState, client: genai.Client, model: str = "gemini-2.5-flash", max_steps: int = 10) -> tuple:
    """
    Executes the custom plan-act loop.
    
    Args:
        goal (str): The user's input/planning objective.
        state (StudyPlannerState): Persistent state containing memory.
        client (genai.Client): Google GenAI client.
        model (str): Gemini model to use.
        max_steps (int): Safety limit to prevent infinite tool-calling loops.
        
    Returns:
        tuple: (final_message, step_trace)
    """
    step_count = len(state.history) + 1
    
    # Custom plan-act loop begins
    for step_idx in range(max_steps):
        # 1. Format the current prompt including the memory/history of past turns
        prompt = format_agent_prompt(goal, state)
        
        try:
            # 2. Call the LLM with system instruction and JSON mode config
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=get_system_instruction(),
                    response_mime_type="application/json",
                    temperature=0.0 # Keep outputs deterministic
                )
            )
            
            # 3. Parse LLM response as JSON
            response_text = response.text.strip()
            response_json = json.loads(response_text)
            
            thought = response_json.get("thought", "")
            action = response_json.get("action", "")
            
            # --- VIVA KEY POINT: The agent decides the next step based on the action ---
            if action == "call_tool":
                tool_name = response_json.get("tool_name")
                tool_args = response_json.get("tool_args", {})
                
                # Check if tool exists
                if tool_name not in TOOL_REGISTRY:
                    observation = f"Error: Tool '{tool_name}' is not supported. Available: {list(TOOL_REGISTRY.keys())}"
                else:
                    # Execute the tool and capture its result as an observation
                    tool_func = TOOL_REGISTRY[tool_name]
                    # We inject the state as the last parameter
                    observation_result = tool_func(**tool_args, state=state)
                    # Convert dict schedule outputs to a string representation for LLM memory
                    if isinstance(observation_result, dict):
                        observation = json.dumps(observation_result)
                    else:
                        observation = str(observation_result)
                
                # Append step to history/memory so the LLM remembers it in the next loop iteration
                state.history.append({
                    "step": step_count,
                    "thought": thought,
                    "action": {"action": action, "tool_name": tool_name, "tool_args": tool_args},
                    "observation": observation
                })
                
                print(f"[Step {step_count}] Called tool '{tool_name}' with args {tool_args}")
                print(f"         Observation: {observation}\n")
                
            elif action == "ask_user":
                message = response_json.get("message", "")
                # The agent needs more input, so it halts the loop and talks to the user
                state.history.append({
                    "step": step_count,
                    "thought": thought,
                    "action": {"action": action, "message": message},
                    "observation": "Waiting for user input."
                })
                print(f"[Step {step_count}] Agent asks user: {message}\n")
                return message, state.history
                
            elif action == "final_answer":
                message = response_json.get("message", "")
                # Goal achieved, save final step and terminate loop
                state.history.append({
                    "step": step_count,
                    "thought": thought,
                    "action": {"action": action, "message": message},
                    "observation": "Plan successfully generated."
                })
                print(f"[Step {step_count}] Final Answer:\n{message}\n")
                return message, state.history
                
            else:
                raise ValueError(f"Unknown action: '{action}'")
                
        except json.JSONDecodeError:
            # If the LLM generates bad JSON, catch the error and feed it back as an observation
            # so the model knows it failed and can re-attempt.
            err_msg = f"Error: Failed to parse your response as JSON. Make sure you return pure JSON."
            state.history.append({
                "step": step_count,
                "thought": "JSON parsing failed.",
                "action": {"action": "parse_failure"},
                "observation": err_msg
            })
            print(f"[Step {step_count}] JSON parsing failed. Retrying...\n")
            
        except Exception as e:
            # General catch-all for tool errors or API connection problems
            err_msg = f"Error: An exception occurred: {str(e)}"
            state.history.append({
                "step": step_count,
                "thought": "Internal error.",
                "action": {"action": "internal_error"},
                "observation": err_msg
            })
            print(f"[Step {step_count}] System error: {str(e)}\n")
            
        step_count += 1
        
    return "Error: Agent reached maximum steps without arriving at a final answer.", state.history
