import os
import json
import traceback
from groq import Groq
from state import StudyPlannerState
import tools

# A mapping of tool names to their actual Python functions
TOOL_REGISTRY = {
    "add_task": tools.add_task,
    "build_schedule": tools.build_schedule,
    "set_study_limit": tools.set_study_limit
}


def get_groq_client(api_key: str = None) -> Groq:
    """
    Initializes and returns a Groq Client.
    Will check for standard environmental variable if API key is not supplied.
    """
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        raise ValueError(
            "GROQ_API_KEY not found. Please set the environment variable "
            "or pass it directly to get_groq_client(api_key='...')."
        )
    return Groq(api_key=key)


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
3. `set_study_limit(hours: float)`
   - Updates the maximum daily study limit allowed in hours.

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
   OR
   {
     "thought": "Brief explanation of why you are setting the daily limit",
     "action": "call_tool",
     "tool_name": "set_study_limit",
     "tool_args": {"hours": 3.0}
   }

2. Ask the user for clarification (mandatory if you lack daily limits or task deadlines):
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
- Daily Study Limit: If the user hasn't explicitly specified how many daily hours they want to study in their input, you MUST use `ask_user` to ask how many hours they can allocate daily. Give them options (1, 2, 3, 4 hours, or specify custom hours) and explain why this is needed.
- Task Deadlines/Due Dates: If the user lists tasks but does not specify due dates or days, check the tasks. Approximate a reasonable deadline offset from the Current Start Date (e.g. 5 days for exams, 2 days for homework/assignments, 7 days for projects). Use `ask_user` to explain these estimated dates to the user and ask: "Do you want to plan till these dates, or would you like to specify custom end dates?"
- Once the user answers your question in a follow-up turn:
  - If they specify their daily hours, call `set_study_limit` to apply it.
  - If they accept your estimated dates or provide custom ones, call `add_task` with those dates.
  - Finally, call `build_schedule` and output your `final_answer`.
- You must call `build_schedule` to generate the schedule structure before providing the `final_answer`.
- Be agentic: Look at task deadlines, ensure study blocks are scheduled BEFORE the task's due date, and report any conflicts or capacity warnings.
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


def run_agent(goal: str, state: StudyPlannerState, client: Groq, model: str = "llama-3.3-70b-versatile", max_steps: int = 10) -> tuple:
    """
    Executes the custom plan-act loop using the Groq API.
    
    Args:
        goal (str): The user's input/planning objective.
        state (StudyPlannerState): Persistent state containing memory.
        client (Groq): Groq API client.
        model (str): Llama model on Groq to use.
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
            # 2. Call the LLM (Groq) with system prompt and JSON mode config
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": get_system_instruction()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0 # Keep outputs deterministic
            )
            
            # 3. Parse LLM response as JSON
            response_text = response.choices[0].message.content.strip()
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
                missing_params = response_json.get("missing_parameters", None)
                # The agent needs more input, so it halts the loop and talks to the user
                state.history.append({
                    "step": step_count,
                    "thought": thought,
                    "action": {
                        "action": action,
                        "message": message,
                        "missing_parameters": missing_params
                    },
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
