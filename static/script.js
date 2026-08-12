// Global State
let currentState = {
    start_date: new Date().toISOString().split('T')[0],
    max_study_hours_per_day: 4.0,
    tasks: [],
    schedule: {},
    history: []
};

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
    traceStepsBadge: document.getElementById('trace-steps-badge')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    // Set default date picker to today
    const todayStr = new Date().toISOString().split('T')[0];
    elements.plannerStartDate.value = todayStr;
    elements.scheduleStartDate.textContent = todayStr;
    currentState.start_date = todayStr;

    // Check API Key
    checkApiKeySetup();
    
    // Add Event Listeners
    setupEventListeners();
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
            
            // Render components
            elements.storedTasksCount.textContent = currentState.tasks.length;
            renderSchedule(currentState.schedule, getWarningsFromHistory(currentState.history));
            renderTrace(currentState.history);
            
            // If the agent asks for input, append helper note or prefill
            const lastStep = currentState.history[currentState.history.length - 1];
            if (lastStep && lastStep.action.action === 'ask_user') {
                elements.agentGoal.value = '';
                elements.agentGoal.placeholder = "Respond to the agent: " + lastStep.action.message;
            } else {
                elements.agentGoal.value = '';
                elements.agentGoal.placeholder = "What is your next study planning goal?";
            }
        }
    } catch (err) {
        console.error(err);
        alert(`Error executing agent: ${err.message}`);
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
