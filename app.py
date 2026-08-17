import os
import json
import sys
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from state import StudyPlannerState
from agent import run_agent, get_groq_client
from test_agent import MockGroqClient

app = FastAPI(title="Study Planner Agent Dashboard")

# Ensure static folder exists
os.makedirs("static", exist_ok=True)

# Define request schemas
class PlanRequest(BaseModel):
    goal: str
    state: Optional[Dict[str, Any]] = None
    model: Optional[str] = "qwen/qwen3.6-27b"
    simulation: Optional[bool] = False

# Simulation Mock Response Lists for the 5 Scenarios
MOCK_SCENARIO_1 = [
    '{"thought": "Extracting Data Structures midterm details.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "Data Structures midterm", "subject": "DSA", "taskType": "exam", "deadline": "2026-08-23", "estimatedHours": 10.0, "durationSource": "user_provided", "deadlineSource": "user_provided", "priority": "high"}}',
    '{"thought": "Extracting DBMS assignment details.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "DBMS assignment", "subject": "DBMS", "taskType": "assignment", "deadline": "2026-08-20", "estimatedHours": 4.0, "durationSource": "user_provided", "deadlineSource": "user_provided", "priority": "medium"}}',
    '{"thought": "Extracting Operating Systems quiz details.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "Operating Systems quiz", "subject": "OS", "taskType": "quiz", "deadline": "2026-08-21", "estimatedHours": 3.0, "durationSource": "user_provided", "deadlineSource": "user_provided", "priority": "medium"}}',
    '{"thought": "Building schedule.", "action": "call_tool", "tool_name": "build_schedule", "tool_args": {}}',
    '{"thought": "Generating final answer.", "action": "final_answer", "message": "What I understood:\\n- Data Structures midterm: due 2026-08-23 (10h requested)\\n- DBMS assignment: due 2026-08-20 (4h requested)\\n- Operating Systems quiz: due 2026-08-21 (3h requested)\\n\\nAssumptions:\\n- All durations and deadlines were explicitly provided by the user."}'
]

MOCK_SCENARIO_2 = [
    '{"thought": "Adding Math Exam task with inferred deadline and default hours.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "Math exam", "subject": "Math", "taskType": "exam", "deadline": "2026-08-24", "estimatedHours": 6.0, "durationSource": "estimated", "deadlineSource": "inferred", "priority": "high"}}',
    '{"thought": "Adding assignment with inferred deadline and default hours.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "Assignment", "subject": "General Study", "taskType": "assignment", "deadline": "2026-08-19", "estimatedHours": 3.0, "durationSource": "estimated", "deadlineSource": "inferred", "priority": "medium"}}',
    '{"thought": "Generating schedule.", "action": "call_tool", "tool_name": "build_schedule", "tool_args": {}}',
    '{"thought": "Generating final answer.", "action": "final_answer", "message": "What I understood:\\n- Math exam: due 2026-08-24 (6h estimated)\\n- General assignment: due 2026-08-19 (3h estimated)\\n\\nAssumptions:\\n- Inferred Math exam deadline to next week (2026-08-24) and estimated 6 hours of study.\\n- Inferred assignment deadline to 2026-08-19 (2 days) and estimated 3 hours of study."}'
]

MOCK_SCENARIO_3 = [
    '{"thought": "Adding DBMS assignment with tomorrow\'s date.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "DBMS assignment", "subject": "DBMS", "taskType": "assignment", "deadline": "2026-08-18", "estimatedHours": 3.0, "durationSource": "estimated", "deadlineSource": "inferred", "priority": "medium"}}',
    '{"thought": "Adding physics quiz with Friday\'s date.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "Physics quiz", "subject": "Physics", "taskType": "quiz", "deadline": "2026-08-21", "estimatedHours": 2.0, "durationSource": "estimated", "deadlineSource": "inferred", "priority": "medium"}}',
    '{"thought": "Generating schedule.", "action": "call_tool", "tool_name": "build_schedule", "tool_args": {}}',
    '{"thought": "Generating final answer.", "action": "final_answer", "message": "What I understood:\\n- DBMS assignment: due 2026-08-18 (3h estimated)\\n- Physics quiz: due 2026-08-21 (2h estimated)\\n\\nAssumptions:\\n- Inferred DBMS assignment deadline to tomorrow (2026-08-18) with 3 hours estimated.\\n- Inferred Physics quiz deadline to Friday (2026-08-21) with 2 hours estimated."}'
]

MOCK_SCENARIO_4 = [
    '{"thought": "Adding DSA revision task with no deadline.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "DSA revision", "subject": "DSA", "taskType": "revision", "deadline": null, "estimatedHours": 2.0, "durationSource": "estimated", "deadlineSource": "missing", "priority": "medium"}}',
    '{"thought": "Adding DBMS revision task.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "DBMS revision", "subject": "DBMS", "taskType": "revision", "deadline": null, "estimatedHours": 2.0, "durationSource": "estimated", "deadlineSource": "missing", "priority": "medium"}}',
    '{"thought": "Adding OS revision task.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "OS revision", "subject": "OS", "taskType": "revision", "deadline": null, "estimatedHours": 2.0, "durationSource": "estimated", "deadlineSource": "missing", "priority": "medium"}}',
    '{"thought": "Generating schedule.", "action": "call_tool", "tool_name": "build_schedule", "tool_args": {}}',
    '{"thought": "Generating final answer.", "action": "final_answer", "message": "What I understood:\\n- DSA revision (2h estimated, no deadline)\\n- DBMS revision (2h estimated, no deadline)\\n- OS revision (2h estimated, no deadline)\\n\\nAssumptions:\\n- Estimated 2 hours for each revision task. Since no deadlines were provided, they have been scheduled in the earliest available slots."}'
]

MOCK_SCENARIO_5 = [
    '{"thought": "Adding Exam preparation with tomorrow\'s deadline.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "Exam preparation", "subject": "General Study", "taskType": "exam", "deadline": "2026-08-18", "estimatedHours": 12.0, "durationSource": "user_provided", "deadlineSource": "inferred", "priority": "high"}}',
    '{"thought": "Generating schedule.", "action": "call_tool", "tool_name": "build_schedule", "tool_args": {}}',
    '{"thought": "Generating final answer.", "action": "final_answer", "message": "What I understood:\\n- Exam preparation: due 2026-08-18 (12h requested)\\n\\nAssumptions:\\n- Inferred exam deadline to tomorrow (2026-08-18).\\n\\nWarnings:\\n- There is an impossible workload conflict! 12 hours cannot fit into a single day before the deadline with your 4-hour daily cap."}'
]

MOCK_DEFAULT = [
    '{"thought": "Adding generic task.", "action": "call_tool", "tool_name": "add_task", "tool_args": {"title": "Study session", "subject": "General Study", "taskType": "general_study", "estimatedHours": 2.0, "priority": "medium"}}',
    '{"thought": "Rebuilding schedule.", "action": "call_tool", "tool_name": "build_schedule", "tool_args": {}}',
    '{"thought": "Final answer.", "action": "final_answer", "message": "What I understood:\\n- Study session (2h estimated)\\n\\nAssumptions:\\n- Assigned default hours for general study session."}'
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
        goal_lower = req.goal.lower()
        if "midterm" in goal_lower or "data structures" in goal_lower:
            mock_responses = MOCK_SCENARIO_1
        elif "math exam next week" in goal_lower or "casual incomplete" in goal_lower:
            mock_responses = MOCK_SCENARIO_2
        elif "tomorrow i need to finish" in goal_lower or "physics quiz this friday" in goal_lower:
            mock_responses = MOCK_SCENARIO_3
        elif "revise dsa" in goal_lower or "timetable" in goal_lower:
            mock_responses = MOCK_SCENARIO_4
        elif "12 hours" in goal_lower or "exam tomorrow" in goal_lower:
            mock_responses = MOCK_SCENARIO_5
        else:
            mock_responses = MOCK_DEFAULT
            
        client = MockGroqClient(mock_responses)
    else:
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
    state = StudyPlannerState(start_date=start_date)
    return {"status": "success", "state": state.to_dict()}

ALLOWED_MODELS = [
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

@app.get("/api/models")
async def list_models(x_groq_api_key: Optional[str] = Header(None)):
    if not x_groq_api_key or x_groq_api_key == "mock":
        return {"models": ALLOWED_MODELS}
    try:
        from groq import Groq
        client = Groq(api_key=x_groq_api_key)
        models_data = client.models.list()
        retrieved_ids = [m.id for m in models_data.data]
        filtered_models = [m for m in ALLOWED_MODELS if m in retrieved_ids]
        if not filtered_models:
            filtered_models = ALLOWED_MODELS
        return {"models": filtered_models}
    except Exception as e:
        return {"models": ALLOWED_MODELS}

# Mount static files to serve index.html, styles, and js
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    static_dir = os.path.join(sys._MEIPASS, 'static')
else:
    static_dir = 'static'

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
