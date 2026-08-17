import datetime
import uuid
import re
from state import StudyPlannerState

# Default estimated hours for missing task durations
DEFAULT_HOURS = {
    "exam": 6.0,
    "quiz": 2.0,
    "assignment": 3.0,
    "homework": 3.0,
    "project": 5.0,
    "presentation": 2.0,
    "revision": 2.0,
    "general_study": 2.0
}

def deterministic_parse_task(text: str, start_date_str: str) -> dict:
    """
    Parses casual goals for dates and hours using deterministic heuristics (regex).
    Protects against timezone shifts and parses phrases like 'due tomorrow'.
    """
    parsed = {}
    
    # Parse base start date
    try:
        start_date = datetime.date.fromisoformat(start_date_str)
    except Exception:
        start_date = datetime.date.today()
        
    text_lower = text.lower()
    
    # 1. Parse hours (patterns: "4h", "4 hours", "need 4 hours", etc.)
    hour_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)', text_lower)
    if hour_match:
        parsed['estimatedHours'] = float(hour_match.group(1))
        parsed['durationSource'] = 'user_provided'
    else:
        # Check text numbers
        word_to_num = {
            "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0, 
            "six": 6.0, "seven": 7.0, "eight": 8.0, "nine": 9.0, "ten": 10.0
        }
        for word, num in word_to_num.items():
            if f"{word} hour" in text_lower or f"{word} h" in text_lower:
                parsed['estimatedHours'] = num
                parsed['durationSource'] = 'user_provided'
                break
                
    # 2. Parse due date (relative and absolute)
    if "tomorrow" in text_lower:
        parsed['deadline'] = (start_date + datetime.timedelta(days=1)).isoformat()
        parsed['deadlineSource'] = 'inferred'
    elif "today" in text_lower:
        parsed['deadline'] = start_date.isoformat()
        parsed['deadlineSource'] = 'inferred'
    elif "day after tomorrow" in text_lower:
        parsed['deadline'] = (start_date + datetime.timedelta(days=2)).isoformat()
        parsed['deadlineSource'] = 'inferred'
    elif "in 3 days" in text_lower or "in three days" in text_lower:
        parsed['deadline'] = (start_date + datetime.timedelta(days=3)).isoformat()
        parsed['deadlineSource'] = 'inferred'
    elif "next week" in text_lower:
        # End of next week (7 days)
        parsed['deadline'] = (start_date + datetime.timedelta(days=7)).isoformat()
        parsed['deadlineSource'] = 'inferred'
    elif "this friday" in text_lower:
        days_ahead = 4 - start_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        parsed['deadline'] = (start_date + datetime.timedelta(days=days_ahead)).isoformat()
        parsed['deadlineSource'] = 'inferred'
    elif "before friday" in text_lower:
        days_ahead = 3 - start_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        parsed['deadline'] = (start_date + datetime.timedelta(days=days_ahead)).isoformat()
        parsed['deadlineSource'] = 'inferred'
    
    # Patterns: 2026-08-23
    iso_match = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', text_lower)
    if iso_match:
        parsed['deadline'] = iso_match.group(1)
        parsed['deadlineSource'] = 'user_provided'
    else:
        # Pattern: 23/08/2026 or 23-08-2026
        slash_match = re.search(r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](20\d{2})\b', text_lower)
        if slash_match:
            d, m, y = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
            try:
                parsed['deadline'] = datetime.date(y, m, d).isoformat()
                parsed['deadlineSource'] = 'user_provided'
            except Exception:
                pass
        else:
            # Pattern: August 23, 23 Aug, etc.
            months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
                      "january", "february", "march", "april", "june", "july", "august", "september", "october", "november", "december"]
            for m_idx, m_name in enumerate(months):
                m_match = re.search(rf'\b({m_name})\b\s*(\d{{1,2}})\b', text_lower)
                if m_match:
                    month_num = (m_idx % 12) + 1
                    day_num = int(m_match.group(2))
                    year = start_date.year
                    try:
                        dt = datetime.date(year, month_num, day_num)
                        if dt < start_date:
                            dt = datetime.date(year + 1, month_num, day_num)
                        parsed['deadline'] = dt.isoformat()
                        parsed['deadlineSource'] = 'user_provided'
                    except Exception:
                        pass
                    break
                m_match_rev = re.search(rf'\b(\d{{1,2}})\s*({m_name})\b', text_lower)
                if m_match_rev:
                    month_num = (m_idx % 12) + 1
                    day_num = int(m_match_rev.group(1))
                    year = start_date.year
                    try:
                        dt = datetime.date(year, month_num, day_num)
                        if dt < start_date:
                            dt = datetime.date(year + 1, month_num, day_num)
                        parsed['deadline'] = dt.isoformat()
                        parsed['deadlineSource'] = 'user_provided'
                    except Exception:
                        pass
                    break
                    
    return parsed

def add_task(
    state: StudyPlannerState,
    title: str,
    id: str = None,
    subject: str = None,
    taskType: str = None,
    deadline: str = None,
    estimatedHours: float = None,
    durationSource: str = None,
    deadlineSource: str = None,
    priority: str = None,
    notes: str = None
) -> str:
    """
    Adds a normalized study task to the planner state. Gracefully applies fallbacks and schema validation.
    """
    # 1. Resolve ID
    task_id = id or uuid.uuid4().hex[:6]
    
    # 2. Resolve Subject (default: General Study)
    task_subject = subject or "General Study"
    if task_subject.strip() == "":
        task_subject = "General Study"
        
    # 3. Resolve Task Type (default: general_study)
    valid_types = ["exam", "quiz", "assignment", "homework", "project", "presentation", "revision", "general_study"]
    task_type = taskType or "general_study"
    if task_type not in valid_types:
        # Check title keywords to infer type
        title_lower = title.lower()
        if "exam" in title_lower or "midterm" in title_lower or "test" in title_lower:
            task_type = "exam"
        elif "quiz" in title_lower:
            task_type = "quiz"
        elif "homework" in title_lower:
            task_type = "homework"
        elif "assignment" in title_lower:
            task_type = "assignment"
        elif "project" in title_lower:
            task_type = "project"
        elif "presentation" in title_lower:
            task_type = "presentation"
        elif "revise" in title_lower or "revision" in title_lower:
            task_type = "revision"
        else:
            task_type = "general_study"

    # 4. Fallback deterministic parsing for date and hours from title or notes
    merged_heuristics = deterministic_parse_task(f"{title} {notes or ''}", state.start_date)

    # 5. Resolve Duration
    task_hours = estimatedHours
    task_dur_source = durationSource
    if task_hours is None or task_hours <= 0:
        if 'estimatedHours' in merged_heuristics:
            task_hours = merged_heuristics['estimatedHours']
            task_dur_source = merged_heuristics['durationSource']
        else:
            task_hours = DEFAULT_HOURS.get(task_type, 2.0)
            task_dur_source = "estimated"
    else:
        task_dur_source = task_dur_source or "user_provided"

    # 6. Resolve Deadline Date
    task_deadline = deadline
    task_dl_source = deadlineSource
    
    # Validate ISO deadline if provided
    if task_deadline:
        # Handle slash dates or format inconsistencies
        if "/" in task_deadline or len(task_deadline.split("-")) != 3:
            parsed_dl = deterministic_parse_task(task_deadline, state.start_date)
            if 'deadline' in parsed_dl:
                task_deadline = parsed_dl['deadline']
                task_dl_source = task_dl_source or parsed_dl['deadlineSource']
            else:
                task_deadline = None
        else:
            try:
                datetime.date.fromisoformat(task_deadline)
                task_dl_source = task_dl_source or "user_provided"
            except Exception:
                task_deadline = None
                
    if not task_deadline:
        if 'deadline' in merged_heuristics:
            task_deadline = merged_heuristics['deadline']
            task_dl_source = task_dl_source or merged_heuristics['deadlineSource']
        else:
            task_deadline = None
            task_dl_source = "missing"

    # 7. Resolve Priority (default: medium)
    task_priority = priority or "medium"
    if task_priority not in ["high", "medium", "low"]:
        task_priority = "medium"

    # Check for duplicate tasks by ID or name + deadline
    for existing in state.tasks:
        if existing["id"] == task_id:
            return f"Task ID {task_id} already exists."
        if existing["title"].lower() == title.lower() and existing["deadline"] == task_deadline:
            return f"Task '{title}' due on {task_deadline} already exists."
            
    # Save structured task
    state.add_task_to_state(
        id=task_id,
        title=title,
        subject=task_subject,
        taskType=task_type,
        deadline=task_deadline,
        estimatedHours=float(task_hours),
        durationSource=task_dur_source,
        deadlineSource=task_dl_source,
        priority=task_priority,
        notes=notes
    )
    
    dl_desc = task_deadline if task_deadline else "No stated deadline"
    return f"Success: Task '{title}' added ({task_hours}h, due: {dl_desc}, priority: {task_priority})."


def build_schedule(state: StudyPlannerState) -> dict:
    """
    Builds a study schedule using a deterministic scheduler.
    Orders tasks with deadlines by Earliest Deadline First (EDF) and priority.
    Appends tasks without deadlines chronologically afterwards.
    Slices study blocks into 30 - 120 minute sessions (0.5 to 2.0 hours).
    """
    if not state.tasks:
        state.schedule = {}
        return {
            "status": "success",
            "message": "No tasks are currently stored.",
            "schedule": {},
            "warnings": []
        }

    try:
        start_date_parsed = datetime.date.fromisoformat(state.start_date)
    except ValueError:
        return {
            "status": "error",
            "message": f"Error: Start date '{state.start_date}' is invalid YYYY-MM-DD.",
            "schedule": {},
            "warnings": []
        }

    # Separate deadline-driven tasks and no-deadline tasks
    deadline_tasks = []
    no_deadline_tasks = []
    
    for t in state.tasks:
        if t.get("deadline"):
            deadline_tasks.append(t)
        else:
            no_deadline_tasks.append(t)

    # Sort priority map
    priority_order = {"high": 3, "medium": 2, "low": 1}

    # Sort deadline-driven tasks: due date first, then priority
    try:
        deadline_tasks_sorted = sorted(
            deadline_tasks,
            key=lambda t: (
                datetime.date.fromisoformat(t["deadline"]),
                -priority_order.get(t.get("priority", "medium"), 2)
            )
        )
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing deadlines: {str(e)}",
            "schedule": {},
            "warnings": []
        }

    # Sort no-deadline tasks: priority first
    no_deadline_tasks_sorted = sorted(
        no_deadline_tasks,
        key=lambda t: -priority_order.get(t.get("priority", "medium"), 2)
    )

    schedule = {}         # YYYY-MM-DD -> list of dicts
    daily_allocated = {}  # YYYY-MM-DD -> float hours
    warnings = []

    # 1. Schedule deadline-driven tasks
    for task in deadline_tasks_sorted:
        task_name = task["title"]
        subject = task["subject"]
        priority = task["priority"]
        notes = task.get("notes", "")
        due_date_parsed = datetime.date.fromisoformat(task["deadline"])
        hours_needed = task["estimatedHours"]

        # Valid study dates starting from start_date_parsed up to due_date_parsed - 1
        study_days = []
        curr = start_date_parsed
        while curr < due_date_parsed:
            study_days.append(curr.isoformat())
            curr += datetime.timedelta(days=1)

        if not study_days:
            # If due today, we can study today
            if due_date_parsed == start_date_parsed:
                study_days = [state.start_date]
            else:
                warnings.append(
                    f"Warning: Task '{task_name}' is due on {task['deadline']}, which is before the schedule start date ({state.start_date}). It cannot be scheduled."
                )
                continue

        allocated_hours = 0.0

        # Pass 1: Try to distribute evenly, up to 2.0 hours max per day (gives variety & slices blocks)
        for day in study_days:
            if allocated_hours >= hours_needed:
                break
            current_day_total = daily_allocated.get(day, 0.0)
            available_capacity = state.max_study_hours_per_day - current_day_total
            if available_capacity <= 0:
                continue

            # Limit allocation to 2.0 hours maximum for block management
            to_allocate = min(hours_needed - allocated_hours, available_capacity, 2.0)
            if to_allocate >= 0.5:  # At least 30 minutes block
                if day not in schedule:
                    schedule[day] = []
                schedule[day].append({
                    "task": task_name,
                    "hours": to_allocate,
                    "subject": subject,
                    "priority": priority,
                    "notes": notes
                })
                daily_allocated[day] = current_day_total + to_allocate
                allocated_hours += to_allocate

        # Pass 2: Fill in remaining capacities of those days if still needed (overriding 2h daily limit per task, but honoring daily cap)
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
                    
                    # Merge if block exists on this day
                    existing = next((item for item in schedule[day] if item["task"] == task_name), None)
                    if existing:
                        existing["hours"] += to_allocate
                    else:
                        schedule[day].append({
                            "task": task_name,
                            "hours": to_allocate,
                            "subject": subject,
                            "priority": priority,
                            "notes": notes
                        })
                    daily_allocated[day] = current_day_total + to_allocate
                    allocated_hours += to_allocate

        # Flag warning if impossible workload/capacity conflict
        if allocated_hours < hours_needed:
            warnings.append(
                f"Warning: Capacity conflict. Could only schedule {allocated_hours:.1f} of {hours_needed:.1f} hours for '{task_name}' before deadline ({task['deadline']})."
            )

    # 2. Schedule no-deadline tasks in remaining capacities chronologically
    for task in no_deadline_tasks_sorted:
        task_name = task["title"]
        subject = task["subject"]
        priority = task["priority"]
        notes = task.get("notes", "")
        hours_needed = task["estimatedHours"]

        allocated_hours = 0.0
        curr_day = start_date_parsed
        
        # Max search window of 60 days to prevent infinite loops
        for _ in range(60):
            if allocated_hours >= hours_needed:
                break
                
            day_str = curr_day.isoformat()
            current_day_total = daily_allocated.get(day_str, 0.0)
            available_capacity = state.max_study_hours_per_day - current_day_total
            
            if available_capacity >= 0.5:
                to_allocate = min(hours_needed - allocated_hours, available_capacity, 2.0)
                if to_allocate > 0:
                    if day_str not in schedule:
                        schedule[day_str] = []
                    schedule[day_str].append({
                        "task": task_name,
                        "hours": to_allocate,
                        "subject": subject,
                        "priority": priority,
                        "notes": notes
                    })
                    daily_allocated[day_str] = current_day_total + to_allocate
                    allocated_hours += to_allocate
                    
            curr_day += datetime.timedelta(days=1)

        if allocated_hours < hours_needed:
            warnings.append(
                f"Warning: Could only schedule {allocated_hours:.1f} of {hours_needed:.1f} hours for no-deadline task '{task_name}' in the 60-day window."
            )

    # Sort schedule chronologically
    sorted_keys = sorted(schedule.keys())
    final_schedule = {day: schedule[day] for day in sorted_keys}
    
    state.schedule = final_schedule

    return {
        "status": "success" if not warnings else "warning",
        "schedule": final_schedule,
        "warnings": warnings,
        "message": f"Successfully built schedule with {len(warnings)} warnings."
    }

def set_study_limit(hours: float, state: StudyPlannerState) -> dict:
    """Updates the maximum study hours limit allowed per day."""
    state.max_study_hours_per_day = float(hours)
    return {
        "status": "success",
        "max_study_hours_per_day": float(hours),
        "message": f"Successfully set daily study limit to {hours} hours."
    }
