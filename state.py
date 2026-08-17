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
        self.tasks = []      # List of dicts: {"name": str, "due": str, "hours_required": float}
        self.schedule = {}   # Dictionary of YYYY-MM-DD -> list of dicts: {"task": str, "hours": float}
        self.history = []    # Trace of agent plan-act loop iterations: [{"step": int, "action": dict, "observation": str}]

    def add_task_to_state(self, name: str, due: str, hours_required: float = 3.0):
        """Helper method to append a task directly to the state."""
        self.tasks.append({
            "name": name,
            "due": due,
            "hours_required": hours_required
        })

    def to_dict(self) -> dict:
        """Serializes the state to a plain dictionary (useful for printing or prompting the LLM)."""
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
