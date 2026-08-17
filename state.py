import datetime
import json

class StudyPlannerState:
    def __init__(self, start_date: str = None, max_study_hours_per_day: float = 4.0):
        """
        State and memory management for the Study Planner Agent.
        
        Args:
            start_date (str): The date from which the schedule starts planning in YYYY-MM-DD format.
                              Defaults to today's date if None.
            max_study_hours_per_day (float): The maximum number of study hours allocated to any single day.
        """
        # Default start date to today's ISO date
        self.start_date = start_date or datetime.date.today().isoformat()
        self.max_study_hours_per_day = max_study_hours_per_day
        self.tasks = []      # List of structured StudyTask dicts
        self.schedule = {}   # Dictionary of YYYY-MM-DD -> list of dicts: {"task": str, "hours": float, ...}
        self.history = []    # Trace of agent plan-act loop iterations

    def add_task_to_state(
        self,
        id: str,
        title: str,
        subject: str,
        taskType: str,
        deadline: str or None,
        estimatedHours: float,
        durationSource: str,
        deadlineSource: str,
        priority: str,
        notes: str = None
    ):
        """Helper method to append a structured task directly to the state."""
        self.tasks.append({
            "id": id,
            "title": title,
            "subject": subject,
            "taskType": taskType,
            "deadline": deadline,
            "estimatedHours": float(estimatedHours),
            "durationSource": durationSource,
            "deadlineSource": deadlineSource,
            "priority": priority,
            "notes": notes
        })

    def to_dict(self) -> dict:
        """Serializes the state to a plain dictionary (useful for prompting the LLM)."""
        return {
            "start_date": self.start_date,
            "max_study_hours_per_day": self.max_study_hours_per_day,
            "tasks": self.tasks,
            "schedule": self.schedule,
            "history": self.history
        }

    def to_json(self) -> str:
        """Serializes the state to a JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def load_from_dict(self, data: dict):
        """Loads state data from a dictionary."""
        self.start_date = data.get("start_date", self.start_date)
        self.max_study_hours_per_day = data.get("max_study_hours_per_day", self.max_study_hours_per_day)
        self.tasks = data.get("tasks", [])
        self.schedule = data.get("schedule", {})
        self.history = data.get("history", [])
