from state import StudyPlannerState
from tools import add_task, build_schedule
import json

def run_test():
    print("=== Testing Study Planner Tools (No LLM) ===")
    
    # 1. Initialize State with start date of 2026-08-11
    state = StudyPlannerState(start_date="2026-08-11", max_study_hours_per_day=4.0)
    print(f"Initialized State. Start date: {state.start_date}, Max study hours/day: {state.max_study_hours_per_day}")
    
    # 2. Add tasks
    print("\nAdding tasks...")
    r1 = add_task("Math Exam", "2026-08-14", state) # Due in 3 days, should take 6 hours
    print(f"Result 1: {r1}")
    
    r2 = add_task("History Homework", "2026-08-13", state) # Due in 2 days, should take 2 hours
    print(f"Result 2: {r2}")
    
    r3 = add_task("Physics Quiz", "2026-08-12", state) # Due tomorrow, should take 2 hours
    print(f"Result 3: {r3}")
    
    # Let's inspect tasks in state
    print(f"\nTasks in State: {json.dumps(state.tasks, indent=2)}")
    
    # 3. Build schedule
    print("\nBuilding schedule...")
    res = build_schedule(state)
    print(f"Status: {res['status']}")
    print(f"Warnings: {res['warnings']}")
    print("\nGenerated Schedule:")
    for date, blocks in res['schedule'].items():
        print(f"  {date}:")
        for b in blocks:
            print(f"    - {b['task']}: {b['hours']} hours")
            
    print("\nFull State JSON representation:")
    print(state.to_json())

if __name__ == "__main__":
    run_test()
