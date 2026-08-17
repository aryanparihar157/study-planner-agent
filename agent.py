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

def safe_print(text: str):
    """
    Safely prints string to standard output, preventing UnicodeEncodeErrors on Windows consoles.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            print(text.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass

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
    return """You are a Study Planner Agent (Topic T24). Your goal is to plan study blocks around user goals.
You must run a plan-act loop, using tools to store tasks and build a schedule, rather than just answering directly.

### Operational Context:
- Current Start Date: provided in the prompt. Use this as the reference current date for calculating relative dates.
- Daily Study Limit (Hours/day): provided in the prompt.

### Tools:
1. `add_task(title: str, id: str = None, subject: str = None, taskType: str = None, deadline: str = None, estimatedHours: float = None, durationSource: str = None, deadlineSource: str = None, priority: str = None, notes: str = None)`
   - Stores a study task.
   - `taskType` MUST be one of: "exam", "quiz", "assignment", "homework", "project", "presentation", "revision", "general_study".
   - `deadline` MUST be YYYY-MM-DD. Convert relative terms ("tomorrow", "next week", "Friday") to absolute YYYY-MM-DD using Current Start Date. If no deadline is stated or inferred, pass null.
   - `estimatedHours`: hours required. Estimate if missing using defaults: exam=6, project=5, assignment/homework=3, quiz/presentation/revision/general_study=2.
   - `durationSource`: "user_provided" or "estimated".
   - `deadlineSource`: "user_provided", "inferred", or "missing".
   - `priority`: "high", "medium", or "low".
   - `notes`: additional info.
2. `build_schedule()`
   - Builds the day-by-day study schedule.
3. `set_study_limit(hours: float)`
   - Updates the maximum daily study limit.

### Output JSON Format:
At each step, you must output a single JSON object. You have three possible actions:

1. Call a tool:
   {
     "thought": "Short operational summary (e.g. 'Extracting DBMS task details')",
     "action": "call_tool",
     "tool_name": "add_task",
     "tool_args": {
       "title": "DBMS Quiz",
       "subject": "DBMS",
       "taskType": "quiz",
       "deadline": "2026-08-20",
       "estimatedHours": 2.0,
       "durationSource": "estimated",
       "deadlineSource": "inferred",
       "priority": "medium",
       "notes": "Weekly review quiz"
     }
   }

2. Ask the user for clarification (only if missing details make scheduling impossible/unreliable):
   {
     "thought": "Short operational summary.",
     "action": "ask_user",
     "message": "Clarification question"
   }

3. Provide the final study plan / answer:
   {
     "thought": "Short operational summary.",
     "action": "final_answer",
     "message": "Friendly study plan summary. MUST include:\n1. 'What I understood' summary showing extracted tasks, due dates, hours.\n2. 'Assumptions' list showing duration/deadline estimates made.\n3. The schedule details."
   }

### Strict Rules:
- You must output VALID JSON. No extra text, markdown formatting blocks around JSON, or explanation outside JSON.
- Do not let your thought expose private reasoning or long chain-of-thought blocks. Keep thoughts short, operational, and safe.
- Safe defaults: Use default hours (6h for exam, 3h for homework, 2h for quiz/revision, etc.) and General Study if user leaves out optional information.
- If relative dates or deadlines are ambiguous, make a reasonable guess, schedule the tasks anyway, and note it in "Assumptions".
- You must call `build_schedule` before presenting the `final_answer`.
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


def run_agent(goal: str, state: StudyPlannerState, client: Groq, model: str = "qwen/qwen3.6-27b", max_steps: int = 10) -> tuple:
    """
    Executes the custom plan-act loop using the Groq API.
    """
    step_count = len(state.history) + 1
    
    # Custom plan-act loop begins
    for step_idx in range(max_steps):
        prompt = format_agent_prompt(goal, state)
        
        try:
            # Call the LLM with system prompt
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": get_system_instruction()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            response_text = response.choices[0].message.content.strip()
            response_json = json.loads(response_text)
            
            thought = response_json.get("thought", "")
            action = response_json.get("action", "")
            
            if action == "call_tool":
                tool_name = response_json.get("tool_name")
                tool_args = response_json.get("tool_args", {})
                
                # Check if tool exists
                if tool_name not in TOOL_REGISTRY:
                    observation = f"Error: Tool '{tool_name}' is not supported. Available: {list(TOOL_REGISTRY.keys())}"
                else:
                    tool_func = TOOL_REGISTRY[tool_name]
                    observation_result = tool_func(**tool_args, state=state)
                    if isinstance(observation_result, dict):
                        observation = json.dumps(observation_result)
                    else:
                        observation = str(observation_result)
                
                state.history.append({
                    "step": step_count,
                    "thought": thought,
                    "action": {"action": action, "tool_name": tool_name, "tool_args": tool_args},
                    "observation": observation
                })
                
                safe_print(f"[Step {step_count}] Called tool '{tool_name}' with args {tool_args}")
                safe_print(f"         Observation: {observation}\n")
                
            elif action == "ask_user":
                message = response_json.get("message", "")
                missing_params = response_json.get("missing_parameters", None)
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
                safe_print(f"[Step {step_count}] Agent asks user: {message}\n")
                return message, state.history
                
            elif action == "final_answer":
                message = response_json.get("message", "")
                state.history.append({
                    "step": step_count,
                    "thought": thought,
                    "action": {"action": action, "message": message},
                    "observation": "Plan successfully generated."
                })
                safe_print(f"[Step {step_count}] Final Answer:\n{message}\n")
                return message, state.history
                
            else:
                raise ValueError(f"Unknown action: '{action}'")
                
        except json.JSONDecodeError:
            err_msg = f"Error: Failed to parse your response as JSON. Make sure you return pure JSON."
            state.history.append({
                "step": step_count,
                "thought": "JSON parsing failed.",
                "action": {"action": "parse_failure"},
                "observation": err_msg
            })
            safe_print(f"[Step {step_count}] JSON parsing failed. Retrying...\n")
            
        except Exception as e:
            available_models = []
            try:
                models_data = client.models.list()
                available_models = [m.id for m in models_data.data]
            except Exception:
                pass
            
            err_msg = f"Error: An exception occurred: {str(e)}"
            if available_models:
                err_msg += f"\n\nAvailable models on your Groq key:\n- " + "\n- ".join(available_models)
                
            state.history.append({
                "step": step_count,
                "thought": "Internal error.",
                "action": {"action": "internal_error"},
                "observation": err_msg
            })
            safe_print(f"[Step {step_count}] System error: {str(e)}\n")
            return f"Error executing agent: {str(e)}", state.history
            
        step_count += 1
        
    return "Error: Agent reached maximum steps without arriving at a final answer.", state.history
