import os
import json
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from state import StudyPlannerState
from agent import run_agent, get_groq_client
# Import mock clients from test_agent for simulation mode
from test_agent import MockGroqClient, MOCK_RESPONSES

app = FastAPI(title="Study Planner Agent Dashboard")

# Ensure static folder exists
os.makedirs("static", exist_ok=True)

# Define request schemas
class PlanRequest(BaseModel):
    goal: str
    state: Optional[Dict[str, Any]] = None
    model: Optional[str] = "llama-3.3-70b-versatile"
    simulation: Optional[bool] = False

# Groq responses for Goal 2 in mock mode
MOCK_RESPONSES_GOAL_2 = [
    '{"thought": "I need to add the new Chemistry Lab task which is due tomorrow on 2026-08-12.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"name": "Chemistry Lab", "due": "2026-08-12"}}',
    '{"thought": "Now that the Chemistry Lab is added alongside the existing Math, History, and Physics tasks, I must rebuild the schedule.", "action": "call_tool", "tool_name": "build_schedule", "tool_args": {}}',
    '{"thought": "The schedule rebuild was successful. Let\'s report the new plan and note that because of the new urgent deadline, we have a capacity warning.", "action": "final_answer", "message": "Re-planning complete! Here is your updated study plan:\\n\\n- **2026-08-11 (Day 1)**:\\n  * Physics Quiz (2.0 hours) - due tomorrow\\n  * Chemistry Lab (2.0 hours) - due tomorrow\\n  *(Note: Day 1 capacity of 4 hours is fully hit; History Homework has been shifted to Day 2)*\\n\\n- **2026-08-12 (Day 2)**:\\n  * History Homework (2.0 hours) - due 2026-08-13\\n  * Math Exam (2.0 hours) - study block 1\\\\n\\n- **2026-08-13 (Day 3)**:\\n  * Math Exam (4.0 hours) - study block 2\\n\\n**Warnings / Capacity Conflicts:**\\n- Warning: Could only schedule 4.0 of 6.0 hours for \'Math Exam\' because Day 1 and Day 2 capacities were filled with closer deadlines. Please consider extending study hours or asking for a Math extension."}'
]

@app.post("/api/plan")
async def plan_schedule(
    req: PlanRequest,
    x_groq_api_key: Optional[str] = Header(None, alias="X-Groq-API-Key")
):
    # 1. Initialize State
    state = StudyPlannerState()
    if req.state:
        state.load_from_dict(req.state)
        
    # 2. Configure Client (Live or Simulation)
    if req.simulation or x_groq_api_key == "mock":
        # Determine mock response set based on history length (first goal vs second re-planning goal)
        if len(state.tasks) > 0:
            mock_responses = MOCK_RESPONSES_GOAL_2
        else:
            mock_responses = MOCK_RESPONSES
        client = MockGroqClient(mock_responses)
    else:
        # Use provided header or environment key
        api_key = x_groq_api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="Groq API Key is required. Please set the GROQ_API_KEY environment variable or enter it in the UI settings."
            )
        try:
            client = get_groq_client(api_key=api_key)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to initialize Groq Client: {str(e)}")

    # 3. Run Agent Loop
    try:
        # Intercept output trace printings and log execution steps
        final_answer, history = run_agent(
            goal=req.goal,
            state=state,
            client=client,
            model=req.model
        )
        
        return {
            "status": "success",
            "final_answer": final_answer,
            "state": state.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Execution Error: {str(e)}")

@app.post("/api/reset")
async def reset_state(start_date: Optional[str] = None):
    # Returns a fresh state dictionary
    state = StudyPlannerState(start_date=start_date)
    return {"status": "success", "state": state.to_dict()}

# Mount static files to serve index.html, styles, and js
app.mount("/", StaticFiles(directory="static", html=True), name="static")
