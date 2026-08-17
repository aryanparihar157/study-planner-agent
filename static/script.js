// Global State
let currentState = {
    start_date: new Date().toISOString().split('T')[0],
    max_study_hours_per_day: 4.0,
    tasks: [],
    schedule: {},
    history: []
};

// LocalStorage Persistence Helpers
function saveStateToLocalStorage() {
    localStorage.setItem('study_planner_state', JSON.stringify(currentState));
}

function sendBrowserNotification(title, body) {
    if (typeof Notification !== 'undefined') {
        if (Notification.permission === 'granted') {
            try {
                new Notification(title, { body: body });
            } catch (e) {
                console.warn("Notification creation failed:", e);
            }
        }
    }
}


function loadStateFromLocalStorage() {
    const savedState = localStorage.getItem('study_planner_state');
    if (savedState) {
        try {
            currentState = JSON.parse(savedState);
            
            // Auto-update start date to today if the saved state date is in the past
            const todayStr = new Date().toISOString().split('T')[0];
            if (currentState.start_date < todayStr) {
                currentState.start_date = todayStr;
                saveStateToLocalStorage(); // Persist the updated date
            }

            // Sync values to sidebar fields
            elements.storedTasksCount.textContent = currentState.tasks.length;
            elements.plannerStartDate.value = currentState.start_date;
            elements.scheduleStartDate.textContent = currentState.start_date;
            elements.maxHoursInput.value = currentState.max_study_hours_per_day;
            // Render components
            renderSchedule(currentState.schedule, getWarningsFromHistory(currentState.history));
            renderTrace(currentState.history);
        } catch (e) {
            console.error("Failed to parse saved state:", e);
        }
    }
}


// DOM Elements
const elements = {
    keyModal: document.getElementById('key-modal'),
    groqApiKeyInput: document.getElementById('groq-api-key'),
    btnSaveKey: document.getElementById('btn-save-key'),
    btnUseSim: document.getElementById('btn-use-sim'),
    btnChangeKey: document.getElementById('btn-change-key'),
    toggleKeyVisibility: document.getElementById('toggle-key-visibility'),
    
    agentGoal: document.getElementById('agent-goal'),
    llmModel: document.getElementById('llm-model'),
    chkSimulation: document.getElementById('chk-simulation'),
    btnExecute: document.getElementById('btn-execute'),
    executeBtnText: document.getElementById('execute-btn-text'),
    executeBtnLoading: document.getElementById('execute-btn-loading'),
    
    storedTasksCount: document.getElementById('stored-tasks-count'),
    scheduleStartDate: document.getElementById('schedule-start-date'),
    maxHoursInput: document.getElementById('max-hours'),
    plannerStartDate: document.getElementById('planner-start-date'),
    btnReset: document.getElementById('btn-reset'),
    
    apiStatusIndicator: document.getElementById('api-status-indicator'),
    scheduleContainer: document.getElementById('schedule-container'),
    traceContainer: document.getElementById('trace-container'),
    traceStepsBadge: document.getElementById('trace-steps-badge'),
    
    // Interactive clarification form elements
    interactiveForm: document.getElementById('interactive-clarification-form'),
    clarificationText: document.getElementById('clarification-question-text'),
    btnSubmitClarification: document.getElementById('btn-submit-clarification'),
    interactiveHoursSection: document.getElementById('interactive-hours-section'),
    interactiveDeadlinesSection: document.getElementById('interactive-deadlines-section'),
    interactiveDeadlinesList: document.getElementById('interactive-deadlines-list'),
    interactiveCustomHours: document.getElementById('interactive-custom-hours')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    // Set default date picker to today
    const todayStr = new Date().toISOString().split('T')[0];
    elements.plannerStartDate.value = todayStr;
    elements.scheduleStartDate.textContent = todayStr;
    currentState.start_date = todayStr;

    // Load State from LocalStorage if it exists (handles today auto-update)
    loadStateFromLocalStorage();

    // Check API Key
    checkApiKeySetup();
    
    // Add Event Listeners
    setupEventListeners();

    // Request Browser Notification Permission on load
    if (typeof Notification !== 'undefined') {
        if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }
});

// Setup Event Listeners
function setupEventListeners() {
    // Modal events
    elements.btnSaveKey.addEventListener('click', saveApiKey);
    elements.btnUseSim.addEventListener('click', useSimulationMode);
    elements.btnChangeKey.addEventListener('click', () => showModal(true));
    elements.toggleKeyVisibility.addEventListener('click', toggleKeyVisibility);
    
    // Config events
    elements.maxHoursInput.addEventListener('change', (e) => {
        currentState.max_study_hours_per_day = parseFloat(e.target.value) || 4.0;
    });
    
    elements.plannerStartDate.addEventListener('change', (e) => {
        const newDate = e.target.value;
        if (newDate) {
            elements.scheduleStartDate.textContent = newDate;
            currentState.start_date = newDate;
        }
    });

    elements.btnReset.addEventListener('click', resetSessionState);
    elements.btnExecute.addEventListener('click', executeAgentAction);
    
    // Checkbox Simulation logic: toggle indicator
    elements.chkSimulation.addEventListener('change', updateApiIndicator);

    // Setup event listeners for interactive hour option buttons
    document.querySelectorAll('.btn-hour-opt').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.btn-hour-opt').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            elements.interactiveCustomHours.value = ''; // clear custom
        });
    });

    elements.interactiveCustomHours.addEventListener('input', () => {
        // Clear active buttons if custom value is typed
        document.querySelectorAll('.btn-hour-opt').forEach(b => b.classList.remove('active'));
    });

    elements.btnSubmitClarification.addEventListener('click', submitClarificationAnswers);
}

// API Key Storage Logic
function checkApiKeySetup() {
    const key = localStorage.getItem('groq_api_key');
    if (!key) {
        showModal(true);
        elements.chkSimulation.checked = true;
    } else {
        showModal(false);
        if (key === 'mock') {
            elements.chkSimulation.checked = true;
        } else {
            elements.chkSimulation.checked = false;
        }
    }
    updateApiIndicator();
}

function showModal(show) {
    if (show) {
        elements.keyModal.classList.remove('hidden');
        // Pre-fill input
        const savedKey = localStorage.getItem('groq_api_key');
        if (savedKey && savedKey !== 'mock') {
            elements.groqApiKeyInput.value = savedKey;
        } else {
            elements.groqApiKeyInput.value = '';
        }
    } else {
        elements.keyModal.classList.add('hidden');
    }
}

function saveApiKey() {
    const key = elements.groqApiKeyInput.value.trim();
    if (!key) {
        alert("Please enter a valid Groq API key or select Simulation Mode.");
        return;
    }
    localStorage.setItem('groq_api_key', key);
    elements.chkSimulation.checked = false;
    showModal(false);
    updateApiIndicator();
}

function useSimulationMode() {
    localStorage.setItem('groq_api_key', 'mock');
    elements.chkSimulation.checked = true;
    showModal(false);
    updateApiIndicator();
}

function toggleKeyVisibility() {
    const type = elements.groqApiKeyInput.type === 'password' ? 'text' : 'password';
    elements.groqApiKeyInput.type = type;
    const icon = elements.toggleKeyVisibility.querySelector('i');
    icon.classList.toggle('fa-eye');
    icon.classList.toggle('fa-eye-slash');
}

function updateApiIndicator() {
    const isSim = elements.chkSimulation.checked;
    const key = localStorage.getItem('groq_api_key');
    
    if (isSim || key === 'mock') {
        elements.apiStatusIndicator.innerHTML = '<span class="status-pill status-simulation"><i class="fa-solid fa-wand-magic-sparkles"></i> Simulation Mode</span>';
    } else if (key) {
        elements.apiStatusIndicator.innerHTML = '<span class="status-pill status-live"><i class="fa-solid fa-circle-check"></i> Groq Live API</span>';
    } else {
        elements.apiStatusIndicator.innerHTML = '<span class="status-pill status-offline"><i class="fa-solid fa-circle"></i> Config Required</span>';
    }
}

// Reset Memory State
async function resetSessionState() {
    if (!confirm("Are you sure you want to clear the agent's memory tasks, history, and schedule?")) {
        return;
    }
    
    const start_date = elements.plannerStartDate.value || new Date().toISOString().split('T')[0];
    
    try {
        const response = await fetch(`/api/reset?start_date=${start_date}`, { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            currentState = data.state;
            saveStateToLocalStorage();
            elements.storedTasksCount.textContent = '0';
            renderSchedule({}, []);
            renderTrace([]);
            elements.agentGoal.value = '';
            alert("Memory reset successful!");
        }
    } catch (err) {
        console.error("Error resetting state:", err);
        alert("Failed to reset session state.");
    }
}

// Execute Agent Planning
async function executeAgentAction() {
    const goal = elements.agentGoal.value.trim();
    if (!goal) {
        alert("Please enter your study goals or assignments first.");
        return;
    }
    
    const isSim = elements.chkSimulation.checked;
    const apiKey = localStorage.getItem('groq_api_key');
    
    if (!isSim && (!apiKey || apiKey === 'mock')) {
        alert("Please save your Groq API Key first or check Simulation Mode.");
        showModal(true);
        return;
    }
    
    // Set loading state
    setLoading(true);
    
    try {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (!isSim && apiKey) {
            headers['X-Groq-API-Key'] = apiKey;
        } else {
            headers['X-Groq-API-Key'] = 'mock'; // Trigger simulation on backend
        }
        
        // Sync config inputs into currentState dict before sending
        currentState.max_study_hours_per_day = parseFloat(elements.maxHoursInput.value) || 4.0;
        currentState.start_date = elements.plannerStartDate.value;
        
        const payload = {
            goal: goal,
            state: currentState,
            model: elements.llmModel.value,
            simulation: isSim
        };
        
        const response = await fetch('/api/plan', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Server error executing agent.");
        }
        
        const result = await response.json();
        if (result.status === 'success') {
            // Update State
            currentState = result.state;
            saveStateToLocalStorage();
            
            // Sync values back to sidebar fields (in case updated by agent tools like set_study_limit)
            elements.plannerStartDate.value = currentState.start_date;
            elements.scheduleStartDate.textContent = currentState.start_date;
            elements.maxHoursInput.value = currentState.max_study_hours_per_day;
            
            // Render components
            elements.storedTasksCount.textContent = currentState.tasks.length;
            const warnings = getWarningsFromHistory(currentState.history);
            renderSchedule(currentState.schedule, warnings);
            renderTrace(currentState.history);
            
            // Notify user of completion, warnings, or clarification queries
            const lastStep = currentState.history[currentState.history.length - 1];
            if (lastStep && lastStep.action.action === 'ask_user') {
                elements.agentGoal.value = '';
                elements.agentGoal.placeholder = "Respond to the agent: " + lastStep.action.message;
                sendBrowserNotification("Study Planner - Clarification Required", lastStep.action.message);
                
                // Show interactive clarification panel if structured missing parameters exist
                showInteractiveClarification(lastStep.action);
            } else {
                // Hide clarification panel if planning is complete
                elements.interactiveForm.classList.add('hidden');
                if (lastStep && lastStep.action.action === 'final_answer') {
                    elements.agentGoal.value = '';
                    elements.agentGoal.placeholder = "What is your next study planning goal?";
                    if (warnings.length > 0) {
                        sendBrowserNotification("Study Planner - Capacity Alert", "Schedule generated with capacity conflicts! Check warning details.");
                    } else {
                        sendBrowserNotification("Study Planner - Success", "Your study schedule has been successfully updated!");
                    }
                }
            }
        }
    } catch (err) {
        console.error(err);
        alert(`Error executing agent: ${err.message}`);
        sendBrowserNotification("Study Planner - Error", `Execution failed: ${err.message}`);
    } finally {
        setLoading(false);
    }
}

function setLoading(loading) {
    if (loading) {
        elements.btnExecute.disabled = true;
        elements.executeBtnText.classList.add('hidden');
        elements.executeBtnLoading.classList.remove('hidden');
    } else {
        elements.btnExecute.disabled = false;
        elements.executeBtnText.classList.remove('hidden');
        elements.executeBtnLoading.classList.add('hidden');
    }
}

// Extract capacity warning logs from built schedule tools observations
function getWarningsFromHistory(history) {
    // Find the build_schedule output inside history observations and extract warnings
    let warnings = [];
    for (let i = history.length - 1; i >= 0; i--) {
        const step = history[i];
        if (step.action.tool_name === 'build_schedule') {
            try {
                const obs = JSON.parse(step.observation);
                if (obs.warnings && obs.warnings.length > 0) {
                    warnings = warnings.concat(obs.warnings);
                }
            } catch (e) {
                // Not JSON or parse fail
            }
        }
    }
    return warnings;
}

// Render visual schedule calendar cards
function renderSchedule(schedule, warnings) {
    elements.scheduleContainer.innerHTML = '';
    
    // Render warnings if they exist
    if (warnings && warnings.length > 0) {
        const warningsDiv = document.createElement('div');
        warningsDiv.className = 'warnings-area';
        warnings.forEach(w => {
            const wItem = document.createElement('div');
            wItem.className = 'warning-item';
            wItem.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <span>${w}</span>`;
            warningsDiv.appendChild(wItem);
        });
        elements.scheduleContainer.appendChild(warningsDiv);
    }
    
    const dates = Object.keys(schedule);
    if (dates.length === 0) {
        elements.scheduleContainer.innerHTML += `
            <div class="empty-state">
                <i class="fa-regular fa-calendar-plus empty-icon"></i>
                <p>No study blocks scheduled yet. Prompt the agent to generate your schedule.</p>
            </div>
        `;
        return;
    }
    
    // Create card grid
    const grid = document.createElement('div');
    grid.className = 'day-cards-grid';
    grid.style.display = 'flex';
    grid.style.flexDirection = 'column';
    grid.style.gap = '14px';
    
    dates.forEach(date => {
        const blocks = schedule[date];
        let totalHours = 0;
        blocks.forEach(b => totalHours += b.hours);
        
        const dayCard = document.createElement('div');
        dayCard.className = 'schedule-day-card';
        
        const dayHeader = document.createElement('div');
        dayHeader.className = 'day-header';
        
        // Format Date
        const dateObj = new Date(date);
        const formattedDate = dateObj.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' });
        
        dayHeader.innerHTML = `
            <span class="date-text">${formattedDate}</span>
            <span class="total-hours"><i class="fa-regular fa-clock"></i> ${totalHours.toFixed(1)}h study</span>
        `;
        
        const dayBlocks = document.createElement('div');
        dayBlocks.className = 'day-blocks';
        
        blocks.forEach(b => {
            const block = document.createElement('div');
            block.className = 'study-block';
            block.innerHTML = `
                <span class="block-title">${b.task}</span>
                <span class="block-duration">${b.hours.toFixed(1)} hrs</span>
            `;
            dayBlocks.appendChild(block);
        });
        
        dayCard.appendChild(dayHeader);
        dayCard.appendChild(dayBlocks);
        grid.appendChild(dayCard);
    });
    
    elements.scheduleContainer.appendChild(grid);
}

// Render Trace logs in real-time
function renderTrace(history) {
    elements.traceContainer.innerHTML = '';
    elements.traceStepsBadge.textContent = `${history.length} steps`;
    
    if (history.length === 0) {
        elements.traceContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-code empty-icon"></i>
                <p>Agent trace will appear here showing thoughts, tool calls, and observations.</p>
            </div>
        `;
        return;
    }
    
    history.forEach(step => {
        const stepDiv = document.createElement('div');
        stepDiv.className = 'trace-step';
        
        let headerText = `Step ${step.step} - Thinking`;
        let icon = '<i class="fa-solid fa-brain"></i>';
        
        const actionType = step.action.action;
        
        if (actionType === 'call_tool') {
            stepDiv.classList.add('tool-call');
            headerText = `Step ${step.step} - Executed Tool (${step.action.tool_name})`;
            icon = '<i class="fa-solid fa-screwdriver-wrench"></i>';
        } else if (actionType === 'final_answer') {
            stepDiv.classList.add('final-answer');
            headerText = `Step ${step.step} - Final Plan Output`;
            icon = '<i class="fa-solid fa-flag-checkered"></i>';
        } else if (actionType === 'ask_user') {
            stepDiv.classList.add('tool-call');
            headerText = `Step ${step.step} - Asked User`;
            icon = '<i class="fa-solid fa-comments"></i>';
        } else if (actionType === 'parse_failure' || actionType === 'internal_error') {
            stepDiv.classList.add('error-step');
            headerText = `Step ${step.step} - Loop Error`;
            icon = '<i class="fa-solid fa-triangle-exclamation"></i>';
        }
        
        let actionDetails = '';
        if (actionType === 'call_tool') {
            actionDetails = `<div class="trace-action">🛠️ Call: <code>${step.action.tool_name}(${JSON.stringify(step.action.tool_args)})</code></div>`;
        } else if (actionType === 'ask_user') {
            actionDetails = `<div class="trace-action">💬 Ask: "${step.action.message}"</div>`;
        }
        
        stepDiv.innerHTML = `
            <div class="trace-header">
                <span>${icon} ${headerText}</span>
            </div>
            <div class="trace-thought">🧠 <em>Thought:</em> "${step.thought}"</div>
            ${actionDetails}
            <div class="trace-observation">👁️ <em>Result:</em> ${step.observation}</div>
        `;
        
        elements.traceContainer.appendChild(stepDiv);
    });
    
    // Auto Scroll to bottom of trace
    elements.traceContainer.scrollTop = elements.traceContainer.scrollHeight;
}

// Show interactive clarification panel
function showInteractiveClarification(action) {
    const missing = action.missing_parameters;
    
    // If no missing parameters structure exists, fallback to standard textarea typing
    if (!missing) {
        elements.interactiveForm.classList.add('hidden');
        return;
    }

    elements.clarificationText.textContent = action.message;
    
    // Toggle study hours section
    if (missing.daily_study_hours) {
        elements.interactiveHoursSection.classList.remove('hidden');
        // Reset selections
        document.querySelectorAll('.btn-hour-opt').forEach(b => b.classList.remove('active'));
        elements.interactiveCustomHours.value = '';
        // Pre-select button based on current state (e.g. if state has 4, pre-select 4)
        const currentCapStr = Math.round(currentState.max_study_hours_per_day).toString();
        const preselectBtn = document.querySelector(`.btn-hour-opt[data-hours="${currentCapStr}"]`);
        if (preselectBtn) {
            preselectBtn.classList.add('active');
        }
    } else {
        elements.interactiveHoursSection.classList.add('hidden');
    }

    // Toggle deadlines list
    if (missing.tasks && missing.tasks.length > 0) {
        elements.interactiveDeadlinesSection.classList.remove('hidden');
        elements.interactiveDeadlinesList.innerHTML = '';
        
        missing.tasks.forEach(task => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'deadline-item';
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = task.name;
            
            const dateInput = document.createElement('input');
            dateInput.type = 'date';
            dateInput.className = 'interactive-deadline-date';
            dateInput.dataset.taskName = task.name;
            // Set date to estimated due date from agent
            dateInput.value = task.estimated_due;
            
            itemDiv.appendChild(nameSpan);
            itemDiv.appendChild(dateInput);
            elements.interactiveDeadlinesList.appendChild(itemDiv);
        });
    } else {
        elements.interactiveDeadlinesSection.classList.add('hidden');
        elements.interactiveDeadlinesList.innerHTML = '';
    }

    // Unhide the panel
    elements.interactiveForm.classList.remove('hidden');
    
    // Smoothly scroll to the clarification form
    elements.interactiveForm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Collect interactive fields and resubmit to agent
function submitClarificationAnswers() {
    // 1. Get chosen study limit
    let studyHours = null;
    const activeBtn = document.querySelector('.btn-hour-opt.active');
    if (activeBtn) {
        studyHours = activeBtn.dataset.hours;
    } else {
        studyHours = elements.interactiveCustomHours.value.trim();
    }

    // 2. Get task due dates
    const deadlineInputs = document.querySelectorAll('.interactive-deadline-date');
    const confirmedTasks = [];
    deadlineInputs.forEach(input => {
        const taskName = input.dataset.taskName;
        const taskDate = input.value;
        confirmedTasks.push({ name: taskName, due: taskDate });
    });

    // 3. Construct text response for the agent
    let promptParts = [];
    if (studyHours) {
        promptParts.push(`I can dedicate ${studyHours} hours daily to study.`);
    }
    if (confirmedTasks.length > 0) {
        const taskStrings = confirmedTasks.map(t => `"${t.name}" is due on ${t.due}`);
        promptParts.push(`Here are the due dates: ${taskStrings.join(', ')}.`);
    } else {
        promptParts.push(`Please proceed with the plan.`);
    }

    const followUpPrompt = promptParts.join(' ');

    // 4. Set prompt, hide form, and execute agent!
    elements.agentGoal.value = followUpPrompt;
    elements.interactiveForm.classList.add('hidden');
    
    // Clear dynamic lists
    elements.interactiveDeadlinesList.innerHTML = '';
    
    // Trigger planning execution
    executeAgentAction();
}
