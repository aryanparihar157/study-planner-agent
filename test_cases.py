import datetime
import json
from state import StudyPlannerState
import tools

def run_tests():
    print("=" * 60)
    print("      STUDY PLANNER AGENT V2 UNIT TEST SUITE")
    print("=" * 60)
    
    # Common test settings
    START_DATE = "2026-08-17"
    DAILY_CAP = 4.0
    
    scenarios = [
        {
            "id": 1,
            "name": "Complete structured input",
            "text": "Data Structures midterm on 2026-08-23 (10h), DBMS assignment on 2026-08-20 (4h), OS quiz on 2026-08-21 (3h)",
            "tasks_to_add": [
                {"title": "Data Structures midterm", "deadline": "2026-08-23", "estimatedHours": 10.0, "priority": "high"},
                {"title": "DBMS assignment", "deadline": "2026-08-20", "estimatedHours": 4.0, "priority": "medium"},
                {"title": "OS quiz", "deadline": "2026-08-21", "estimatedHours": 3.0, "priority": "medium"}
            ]
        },
        {
            "id": 2,
            "name": "Casual incomplete input",
            "text": "I have a math exam next week and an assignment due soon.",
            "tasks_to_add": [
                # Simulate parsing math exam next week and general assignment soon
                {"title": "Math exam (next week)", "deadline": "2026-08-24", "estimatedHours": None, "taskType": "exam", "priority": "high"},
                {"title": "Assignment (soon)", "deadline": "2026-08-19", "estimatedHours": None, "taskType": "assignment", "priority": "medium"}
            ]
        },
        {
            "id": 3,
            "name": "Relative dates",
            "text": "Tomorrow DBMS assignment, physics quiz this Friday.",
            "tasks_to_add": [
                # Tomorrow DBMS assignment, physics quiz this Friday
                {"title": "DBMS assignment", "deadline": "2026-08-18", "estimatedHours": 3.0, "priority": "medium"},
                {"title": "Physics quiz", "deadline": "2026-08-21", "estimatedHours": 2.0, "priority": "medium"}
            ]
        },
        {
            "id": 4,
            "name": "No deadlines",
            "text": "I need to revise DSA, DBMS, and OS. Make a timetable.",
            "tasks_to_add": [
                {"title": "DSA revision", "deadline": None, "estimatedHours": None, "taskType": "revision", "priority": "medium"},
                {"title": "DBMS revision", "deadline": None, "estimatedHours": None, "taskType": "revision", "priority": "medium"},
                {"title": "OS revision", "deadline": None, "estimatedHours": None, "taskType": "revision", "priority": "medium"}
            ]
        },
        {
            "id": 5,
            "name": "Impossible workload",
            "text": "I have an exam tomorrow and need 12 hours of preparation.",
            "tasks_to_add": [
                {"title": "Exam preparation", "deadline": "2026-08-18", "estimatedHours": 12.0, "taskType": "exam", "priority": "high"}
            ]
        }
    ]
    
    all_passed = True
    
    for sc in scenarios:
        print(f"\n--- Running Scenario {sc['id']}: {sc['name']} ---")
        print(f"Goal: {sc['text']}")
        
        # 1. Initialize fresh state
        state = StudyPlannerState(start_date=START_DATE, max_study_hours_per_day=DAILY_CAP)
        
        # 2. Add tasks
        for t_args in sc["tasks_to_add"]:
            res = tools.add_task(state=state, **t_args)
            print(f"  Add Task Result: {res}")
            
        # Verify parser properties
        for task in state.tasks:
            # Check structure matches StudyTask schema
            assert "id" in task, "Task missing id"
            assert "title" in task, "Task missing title"
            assert "subject" in task, "Task missing subject"
            assert "estimatedHours" in task, "Task missing estimatedHours"
            assert "durationSource" in task, "Task missing durationSource"
            assert "deadlineSource" in task, "Task missing deadlineSource"
            assert "priority" in task, "Task missing priority"
            
            # Check default hours fallback logic
            if task["estimatedHours"] <= 0 or task["estimatedHours"] is None:
                all_passed = False
                print(f"  [FAIL] Task '{task['title']}' has invalid estimated hours.")
        
        # 3. Build schedule
        sch_res = tools.build_schedule(state)
        schedule = sch_res["schedule"]
        warnings = sch_res["warnings"]
        
        print(f"  Schedule Build: {sch_res['status']}")
        if warnings:
            print(f"  Warnings: {warnings}")
            
        # 4. Perform Verifications
        sc_passed = True
        
        # Verify start date is respected
        for day in schedule.keys():
            if day < START_DATE:
                sc_passed = False
                print(f"  [FAIL] Scheduled slot {day} before start date {START_DATE}.")
                
        # Verify daily cap is never exceeded
        for day, blocks in schedule.items():
            day_total = sum(b["hours"] for b in blocks)
            if day_total > DAILY_CAP + 0.01:
                sc_passed = False
                print(f"  [FAIL] Day {day} total hours ({day_total}) exceeds cap ({DAILY_CAP}).")
                
        # Verify study blocks are created before deadlines
        for day, blocks in schedule.items():
            for block in blocks:
                # Find matching task in state
                task = next((t for t in state.tasks if t["title"] == block["task"]), None)
                if task and task["deadline"]:
                    if day >= task["deadline"]:
                        sc_passed = False
                        print(f"  [FAIL] Scheduled block for '{task['title']}' on {day} which is at/after deadline {task['deadline']}.")

        # Verify impossible plan produces warning
        if sc["id"] == 5:
            if not warnings or not any("Capacity conflict" in w for w in warnings):
                sc_passed = False
                print(f"  [FAIL] Scenario 5 (12h workload) did not trigger expected capacity conflict warning.")
            else:
                print(f"  [PASS] Correctly detected and logged capacity conflict warning.")

        if sc_passed:
            print(f"  [PASS] Scenario {sc['id']} verification checks passed.")
        else:
            all_passed = False
            print(f"  [FAIL] Scenario {sc['id']} verification checks failed.")
            
        # Display sample schedule output
        print("  Generated Slots:")
        for day, blocks in schedule.items():
            blk_str = ", ".join([f"{b['task']} ({b['hours']}h)" for b in blocks])
            print(f"    - {day}: {blk_str}")
            
    print("\n" + "="*60)
    if all_passed:
        print("      ALL SCENARIOS VERIFICATION TESTS PASSED SUCCESSFULLY!")
    else:
        print("      SOME SCENARIO TESTS FAILED. PLEASE REVIEW CHECKS.")
    print("="*60)

if __name__ == "__main__":
    run_tests()
