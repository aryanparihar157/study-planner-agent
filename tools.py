import datetime
from state import StudyPlannerState

def add_task(name: str, due: str, state: StudyPlannerState) -> str:
    """
    Store a task with its due date in the planner state.
    
    Args:
        name (str): The name or description of the task (e.g. 'Math Exam', 'Lab Report').
        due (str): The due date in YYYY-MM-DD format.
        state (StudyPlannerState): The current state of the agent.
        
    Returns:
        str: A confirmation message of whether the task was successfully added or if an error occurred.
    """
    # Validate the date format
    try:
        due_date = datetime.date.fromisoformat(due)
    except ValueError:
        return f"Error: Due date '{due}' is not in YYYY-MM-DD format. Task was NOT added."
    
    # Check for duplicate tasks on the same due date
    for existing in state.tasks:
        if existing["name"].lower() == name.lower() and existing["due"] == due:
            return f"Task '{name}' due on {due} already exists in the system."
            
    # Determine default hours based on keywords in task name
    name_lower = name.lower()
    if "exam" in name_lower or "test" in name_lower or "final" in name_lower:
        hours = 6.0
    elif "project" in name_lower or "presentation" in name_lower:
        hours = 4.0
    elif "quiz" in name_lower or "homework" in name_lower or "assignment" in name_lower:
        hours = 2.0
    else:
        hours = 3.0  # standard default

    state.add_task_to_state(name, due, hours_required=hours)
    return f"Success: Task '{name}' added with {hours} estimated study hours required, due on {due}."


def build_schedule(state: StudyPlannerState) -> dict:
    """
    Build a study schedule from all stored tasks, ordering tasks by deadline
    and distributing study blocks before each due date.
    
    Args:
        state (StudyPlannerState): The current state of the agent containing tasks.
        
    Returns:
        dict: A dictionary containing the status, any warnings (conflicts), and the day-by-day study schedule.
    """
    if not state.tasks:
        state.schedule = {}
        return {
            "status": "success",
            "message": "No tasks are currently stored. Add tasks before building a schedule.",
            "schedule": {},
            "warnings": []
        }
        
    try:
        start_date_parsed = datetime.date.fromisoformat(state.start_date)
    except ValueError:
        return {
            "status": "error",
            "message": f"Error: Start date '{state.start_date}' in state is invalid YYYY-MM-DD.",
            "schedule": {},
            "warnings": []
        }
        
    # Order tasks by due date (Earliest Deadline First - EDF)
    try:
        sorted_tasks = sorted(state.tasks, key=lambda t: datetime.date.fromisoformat(t["due"]))
    except ValueError as e:
        return {
            "status": "error",
            "message": f"Error: One or more tasks have invalid due dates. Details: {str(e)}",
            "schedule": {},
            "warnings": []
        }
        
    schedule = {}         # YYYY-MM-DD -> list of dicts: {"task": name, "hours": float}
    daily_allocated = {}  # YYYY-MM-DD -> float (running total of hours allocated on that day)
    warnings = []
    
    for task in sorted_tasks:
        task_name = task["name"]
        due_date_parsed = datetime.date.fromisoformat(task["due"])
        hours_needed = task["hours_required"]
        
        # Calculate valid study days: starting from state.start_date up to the day BEFORE due_date
        study_days = []
        curr = start_date_parsed
        while curr < due_date_parsed:
            study_days.append(curr.isoformat())
            curr += datetime.timedelta(days=1)
            
        if not study_days:
            # If the task is due on the start_date itself, we can study on the start_date
            if due_date_parsed == start_date_parsed:
                study_days = [state.start_date]
            else:
                warnings.append(
                    f"Task '{task_name}' is due on {task['due']}, which is before the current schedule "
                    f"start date ({state.start_date}). No study blocks could be scheduled for it."
                )
                continue
                
        # Attempt to distribute hours backwards from the deadline (best practice for memory retention)
        # Or chronologically, let's go chronologically first but distribute tasks evenly.
        # Let's allocate hours in blocks of at most 2.0 hours per task per day to keep variety,
        # but repeat until the task's required hours are satisfied.
        allocated_hours = 0.0
        
        # Phase 1: Try to allocate up to 2.0 hours per day (gives variety)
        for day in study_days:
            if allocated_hours >= hours_needed:
                break
            current_day_total = daily_allocated.get(day, 0.0)
            available_capacity = state.max_study_hours_per_day - current_day_total
            if available_capacity <= 0:
                continue
                
            to_allocate = min(hours_needed - allocated_hours, available_capacity, 2.0)
            if to_allocate > 0:
                if day not in schedule:
                    schedule[day] = []
                schedule[day].append({"task": task_name, "hours": to_allocate})
                daily_allocated[day] = current_day_total + to_allocate
                allocated_hours += to_allocate
                
        # Phase 2: If we still need hours, fill the remaining capacity of the days without the 2.0 hour limit
        if allocated_hours < hours_needed:
            for day in study_days:
                if allocated_hours >= hours_needed:
                    break
                current_day_total = daily_allocated.get(day, 0.0)
                available_capacity = state.max_study_hours_per_day - current_day_total
                if available_capacity <= 0:
                    continue
                    
                to_allocate = min(hours_needed - allocated_hours, available_capacity)
                if to_allocate > 0:
                    if day not in schedule:
                        schedule[day] = []
                    # Check if task already has a block on this day, if so merge them
                    existing = next((item for item in schedule[day] if item["task"] == task_name), None)
                    if existing:
                        existing["hours"] += to_allocate
                    else:
                        schedule[day].append({"task": task_name, "hours": to_allocate})
                    daily_allocated[day] = current_day_total + to_allocate
                    allocated_hours += to_allocate
                    
        # Check if the task could be fully scheduled
        if allocated_hours < hours_needed:
            warnings.append(
                f"Warning: Could only schedule {allocated_hours:.1f} of {hours_needed:.1f} hours for '{task_name}' "
                f"due to study limits (Max {state.max_study_hours_per_day}h/day)."
            )
            
    # Sort the final schedule chronologically by day
    sorted_keys = sorted(schedule.keys())
    final_schedule = {day: schedule[day] for day in sorted_keys}
    
    state.schedule = final_schedule
    
    return {
        "status": "success" if not warnings else "warning",
        "schedule": final_schedule,
        "warnings": warnings,
        "message": f"Successfully built schedule with {len(warnings)} warnings."
    }

def set_study_limit(hours: float, state) -> dict:
    """Updates the maximum study hours limit allowed per day."""
    state.max_study_hours_per_day = float(hours)
    return {
        "status": "success",
        "max_study_hours_per_day": float(hours),
        "message": f"Successfully set daily study limit to {hours} hours."
    }
