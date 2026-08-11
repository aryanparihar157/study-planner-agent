# CSE476 Study Planner Agent (Topic T24)

This project implements an agentic study planner with a custom plan-act loop in plain Python. It schedules study blocks around deadlines using the Google GenAI SDK.

### Tools Implemented
The agent utilizes two tools written in pure Python:
1. `add_task(name, due, state)`: Validates tasks and their deadlines (in YYYY-MM-DD format), calculates study hours needed based on task type keywords, and stores them in the state.
2. `build_schedule(state)`: Implements an Earliest Deadline First (EDF) scheduling algorithm. It automatically sorts tasks, allocates daily study blocks before the task is due, respects a maximum daily capacity, and returns warning flags if deadlines are too tight to fit.

### Memory Design
The agent's memory is managed by the `StudyPlannerState` class, which persists across the entire user session. It stores a list of current tasks, the generated schedule, and a chronological history of the agent's actions (including steps, thoughts, tool calls, and tool observations). Because this state is passed into the agent loop on every turn, the agent can remember tasks added in earlier queries and re-schedule them dynamically when new tasks are added.

### Honest Failure and Resolution
One major failure we encountered was that the LLM's JSON-formatted responses sometimes contained invalid JSON escape characters (such as escaping single quotes `\'` or having unescaped line breaks), which crashed standard Python `json.loads()` calls. To handle this, we wrapped the JSON parsing block in a `try-except JSONDecodeError` block within the plan-act loop. Instead of crashing, the agent records the parsing error as an observation (e.g., *"Error: Failed to parse response as JSON"*), appends it to the history, and prompts the model again. In the subsequent turn, the model reads its own execution history, recognizes the formatting failure, and outputs corrected, valid JSON, allowing the agent to self-heal.
