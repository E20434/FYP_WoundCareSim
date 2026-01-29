// Configuration
const API_BASE_URL = 'http://localhost:8000';

// Global State
let currentSession = {
    sessionId: null,
    scenarioId: null,
    currentStep: null,
    nextStep: null,
    scenarioMetadata: null,
    mcqQuestions: [],
    actionCounter: { cleaning: 0, dressing: 0 }
};

// ==========================================
// Utility Functions
// ==========================================

function showLoading() {
    document.getElementById('loadingSpinner').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingSpinner').style.display = 'none';
}

function showScreen(screenId) {
    // Hide all screens
    const screens = document.querySelectorAll('.screen');
    screens.forEach(screen => screen.style.display = 'none');
    
    // Show requested screen
    document.getElementById(screenId).style.display = 'block';
}

function showError(message) {
    alert('Error: ' + message);
}

function handleEnter(event, callback) {
    if (event.key === 'Enter') {
        callback();
    }
}

async function apiCall(endpoint, method = 'GET', body = null) {
    showLoading();
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }
        
        const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showError(error.message);
        throw error;
    } finally {
        hideLoading();
    }
}

// ==========================================
// Session Management
// ==========================================

async function startSession() {
    const scenarioId = document.getElementById('scenarioId').value.trim();
    const studentId = document.getElementById('studentId').value.trim();
    
    if (!scenarioId || !studentId) {
        showError('Please enter both Scenario ID and Student ID');
        return;
    }
    
    try {
        const response = await apiCall('/session/start', 'POST', {
            scenario_id: scenarioId,
            student_id: studentId
        });
        
        currentSession.sessionId = response.session_id;
        currentSession.scenarioId = scenarioId;
        
        // Fetch session details
        await loadSessionInfo();
        
        // Start with HISTORY step
        showHistoryStep();
        
    } catch (error) {
        console.error('Failed to start session:', error);
    }
}

async function loadSessionInfo() {
    try {
        const session = await apiCall(`/session/${currentSession.sessionId}`);
        
        currentSession.currentStep = session.current_step;
        currentSession.scenarioMetadata = session.scenario_metadata;
        currentSession.mcqQuestions = session.scenario_metadata.assessment_questions || [];
        
        // Update UI
        document.getElementById('sessionInfo').style.display = 'flex';
        document.getElementById('sessionId').textContent = currentSession.sessionId;
        document.getElementById('currentStep').textContent = currentSession.currentStep;
        document.getElementById('scenarioTitle').textContent = session.scenario_metadata.title || 'Unknown';
        
    } catch (error) {
        console.error('Failed to load session info:', error);
    }
}

// ==========================================
// HISTORY Step
// ==========================================

function showHistoryStep() {
    currentSession.currentStep = 'history'; // Update session state
    showScreen('historyScreen');
    document.getElementById('currentStep').textContent = 'history';
    
    // Clear conversation box
    const conversationBox = document.getElementById('conversationBox');
    conversationBox.innerHTML = '<div class="conversation-empty">Start by asking the patient a question...</div>';
}

async function sendMessage() {
    const input = document.getElementById('patientQuestion');
    const message = input.value.trim();
    
    if (!message) return;
    
    try {
        // Add student message to UI
        addMessageToConversation('student', message);
        input.value = '';
        
        // Send to backend
        const response = await apiCall('/session/message', 'POST', {
            session_id: currentSession.sessionId,
            message: message
        });
        
        // Add patient response
        addMessageToConversation('patient', response.patient_response);
        
    } catch (error) {
        console.error('Failed to send message:', error);
    }
}

function addMessageToConversation(speaker, text) {
    const conversationBox = document.getElementById('conversationBox');
    
    // Remove empty state if present
    const emptyState = conversationBox.querySelector('.conversation-empty');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${speaker}`;
    messageDiv.innerHTML = `
        <div class="message-speaker">${speaker === 'student' ? 'You' : 'Patient'}:</div>
        <div>${text}</div>
    `;
    
    conversationBox.appendChild(messageDiv);
    conversationBox.scrollTop = conversationBox.scrollHeight;
}

// ==========================================
// ASSESSMENT Step
// ==========================================

function showAssessmentStep() {
    currentSession.currentStep = 'assessment'; // Update session state
    showScreen('assessmentScreen');
    document.getElementById('currentStep').textContent = 'assessment';
    
    // Load MCQ questions
    loadMCQQuestions();
}

function loadMCQQuestions() {
    const container = document.getElementById('mcqContainer');
    container.innerHTML = '';
    
    if (!currentSession.mcqQuestions || currentSession.mcqQuestions.length === 0) {
        container.innerHTML = '<p class="text-muted">No assessment questions available.</p>';
        return;
    }
    
    currentSession.mcqQuestions.forEach((question, index) => {
        const questionDiv = document.createElement('div');
        questionDiv.className = 'mcq-question';
        questionDiv.id = `mcq-${question.id}`;
        
        questionDiv.innerHTML = `
            <div class="mcq-header">
                <span class="question-number">Question ${index + 1} of ${currentSession.mcqQuestions.length}</span>
                <span class="mcq-status" id="status-${question.id}" style="display: none;"></span>
            </div>
            <div class="question-text">${question.question}</div>
            <div class="mcq-options" id="options-${question.id}">
                ${question.options.map(option => `
                    <div class="mcq-option" onclick="selectMCQOption('${question.id}', '${option}')">
                        ${option}
                    </div>
                `).join('')}
            </div>
            <div class="mcq-feedback" id="feedback-${question.id}" style="display: none;"></div>
        `;
        
        container.appendChild(questionDiv);
    });
}

async function selectMCQOption(questionId, answer) {
    try {
        // Submit answer
        const response = await apiCall('/session/mcq-answer', 'POST', {
            session_id: currentSession.sessionId,
            question_id: questionId,
            answer: answer
        });
        
        // Update UI
        const questionDiv = document.getElementById(`mcq-${questionId}`);
        const optionsDiv = document.getElementById(`options-${questionId}`);
        const statusSpan = document.getElementById(`status-${questionId}`);
        const feedbackDiv = document.getElementById(`feedback-${questionId}`);
        
        // Disable all options
        const options = optionsDiv.querySelectorAll('.mcq-option');
        options.forEach(opt => {
            opt.classList.add('disabled');
            if (opt.textContent.trim() === answer) {
                opt.classList.add('selected');
            }
        });
        
        // Show status
        statusSpan.style.display = 'block';
        statusSpan.className = `mcq-status ${response.status}`;
        statusSpan.textContent = response.is_correct ? 'Correct' : 'Incorrect';
        
        // Mark question as answered
        questionDiv.classList.add('answered', response.status);
        
        // Show feedback
        feedbackDiv.style.display = 'block';
        feedbackDiv.className = `mcq-feedback ${response.status}`;
        feedbackDiv.innerHTML = `
            <span class="feedback-label">${response.is_correct ? 'Correct!' : 'Incorrect'}</span>
            <p><strong>Correct Answer:</strong> ${response.correct_answer}</p>
            <p><strong>Explanation:</strong> ${response.explanation}</p>
        `;
        
    } catch (error) {
        console.error('Failed to submit MCQ answer:', error);
    }
}

// ==========================================
// CLEANING Step
// ==========================================

function showCleaningStep() {
    currentSession.currentStep = 'cleaning'; // Update session state
    showScreen('cleaningScreen');
    document.getElementById('currentStep').textContent = 'cleaning';
    currentSession.actionCounter.cleaning = 0;
    
    // Load cleaning actions
    loadCleaningActions();
}

function loadCleaningActions() {
    const container = document.getElementById('cleaningActions');
    
    const cleaningActions = [
        { type: 'handwash_1', label: '1. Perform Medical Hand Washing (First Time)' },
        { type: 'arrange_trolley', label: '2. Arrange Dressing Trolley' },
        { type: 'handwash_2', label: '3. Perform Medical Hand Washing (Second Time)' },
        // Step 4: ASK staff nurse to verify cleaning solution (done via chat)
        { type: 'bring_trolley', label: '5. Bring Trolley to Patient Area' },
        { type: 'clean_center_to_periphery', label: '6. Clean Wound (Center to Periphery)' },
        { type: 'dispose_materials', label: '7. Dispose Contaminated Materials' }
    ];
    
    container.innerHTML = '';
    cleaningActions.forEach(action => {
        const button = document.createElement('button');
        button.className = 'action-btn';
        button.onclick = () => recordAction(action.type, 'cleaning');
        button.innerHTML = `
            <span class="checkmark">âœ”</span>
            <span>${action.label}</span>
        `;
        container.appendChild(button);
    });
}

async function recordAction(actionType, step) {
    try {
        const response = await apiCall('/session/action', 'POST', {
            session_id: currentSession.sessionId,
            action_type: actionType,
            metadata: { timestamp: new Date().toISOString() }
        });
        
        // Update counter
        currentSession.actionCounter[step] = response.total_actions;
        document.getElementById(`${step}Counter`).textContent = response.total_actions;
        
        // Visual feedback on button
        event.target.closest('.action-btn').classList.add('clicked');
        
    } catch (error) {
        console.error('Failed to record action:', error);
    }
}

// ==========================================
// DRESSING Step
// ==========================================

function showDressingStep() {
    currentSession.currentStep = 'dressing'; // Update session state
    showScreen('dressingScreen');
    document.getElementById('currentStep').textContent = 'dressing';
    currentSession.actionCounter.dressing = 0;
    
    // Load dressing actions
    loadDressingActions();
}

function loadDressingActions() {
    const container = document.getElementById('dressingActions');
    
    const dressingActions = [
        { type: 'handwash_before', label: '1. Perform Hand Washing (Before Dressing)' },
        // Step 2: ASK staff nurse to verify sterile dressing packet (done via chat)
        { type: 'apply_dressing', label: '3. Apply Dressing to Wound' },
        { type: 'handwash_after', label: '4. Perform Hand Washing (After Dressing)' }
    ];
    
    container.innerHTML = '';
    dressingActions.forEach(action => {
        const button = document.createElement('button');
        button.className = 'action-btn';
        button.onclick = () => recordAction(action.type, 'dressing');
        button.innerHTML = `
            <span class="checkmark">âœ”</span>
            <span>${action.label}</span>
        `;
        container.appendChild(button);
    });
}

// ==========================================
// Staff Nurse
// ==========================================

async function askStaffNurse() {
    const step = currentSession.currentStep;
    const inputId = `nurseQuestion${step.charAt(0).toUpperCase() + step.slice(1)}`;
    const responseId = `staffNurse${step.charAt(0).toUpperCase() + step.slice(1)}`;
    
    const input = document.getElementById(inputId);
    const message = input.value.trim();
    
    if (!message) return;
    
    try {
        const response = await apiCall('/session/staff-nurse', 'POST', {
            session_id: currentSession.sessionId,
            message: message
        });
        
        // Display response
        const responseDiv = document.getElementById(responseId);
        responseDiv.innerHTML = `
            <strong>Staff Nurse:</strong>
            <p>${response.staff_nurse_response}</p>
        `;
        
        input.value = '';
        
    } catch (error) {
        console.error('Failed to ask staff nurse:', error);
    }
}

// ==========================================
// Step Completion
// ==========================================

async function finishStep(step) {
    try {
        const response = await apiCall('/session/step', 'POST', {
            session_id: currentSession.sessionId,
            step: step
        });
        
        // Store next step
        currentSession.nextStep = response.next_step;
        
        // Show feedback modal
        displayFeedback(response.evaluation);
        
    } catch (error) {
        console.error('Failed to finish step:', error);
    }
}

function displayFeedback(evaluation) {
    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    
    let html = '';
    
    // ASSESSMENT step: MCQ-only display (no agent feedback, no scores)
    if (evaluation.step === 'assessment' && evaluation.mcq_result) {
        html += `
            <div class="feedback-section">
                <h3>MCQ Assessment Results</h3>
                <div class="mcq-summary">
                    <div class="mcq-summary-header">
                        <span><strong>Summary:</strong> ${evaluation.mcq_result.summary}</span>
                        <span class="mcq-score-display">${evaluation.mcq_result.correct_count}/${evaluation.mcq_result.total_questions}</span>
                    </div>
                    <div class="mcq-results">
        `;
        
        if (evaluation.mcq_result.feedback) {
            evaluation.mcq_result.feedback.forEach(item => {
                const statusClass = item.status === 'correct' ? 'correct' : 
                                   item.status === 'incorrect' ? 'incorrect' : 'not_answered';
                const statusText = item.status === 'correct' ? 'Correct' : 
                                  item.status === 'incorrect' ? 'Incorrect' : 'Not Answered';
                
                html += `
                    <div class="mcq-result-item ${statusClass}">
                        <strong>Q: ${item.question}</strong><br>
                        <span class="mcq-status-badge ${statusClass}">${statusText}</span><br>
                        ${item.student_answer ? `Your answer: ${item.student_answer}<br>` : ''}
                        Correct answer: ${item.correct_answer}<br>
                        <em>${item.explanation}</em>
                    </div>
                `;
            });
        }
        
        html += `</div></div></div>`;
        
        content.innerHTML = html;
        modal.style.display = 'flex';
        return;
    }
    
    // OTHER STEPS: Normal agent feedback display
    
    // Narrated Feedback (Primary)
    if (evaluation.narrated_feedback) {
        html += `
            <div class="feedback-section">
                <h3>Feedback Summary</h3>
                <div class="narrated-feedback">
                    ${evaluation.narrated_feedback.message_text}
                </div>
            </div>
        `;
    }
    
    // Scores
    if (evaluation.scores) {
        html += `
            <div class="feedback-section">
                <h3>Performance Scores</h3>
                <div class="scores-display">
        `;
        
        // Agent scores
        if (evaluation.scores.agent_scores) {
            for (const [agent, score] of Object.entries(evaluation.scores.agent_scores)) {
                const displayName = agent.replace('Agent', '');
                html += `
                    <div class="score-card">
                        <div class="score-label">${displayName}</div>
                        <div class="score-value">${score.toFixed(2)}</div>
                        <div class="score-bar">
                            <div class="score-fill" style="width: ${score * 100}%"></div>
                        </div>
                    </div>
                `;
            }
        }
        
        // Overall score
        if (evaluation.scores.step_quality_indicator !== undefined) {
            html += `
                <div class="score-card">
                    <div class="score-label">Overall Quality</div>
                    <div class="score-value">${evaluation.scores.step_quality_indicator.toFixed(2)}</div>
                    <div class="score-bar">
                        <div class="score-fill" style="width: ${evaluation.scores.step_quality_indicator * 100}%"></div>
                    </div>
                </div>
            `;
        }
        
        html += `</div></div>`;
    }
    
    // Raw Feedback (Detailed) - NOT for ASSESSMENT step
    if (evaluation.raw_feedback && evaluation.raw_feedback.length > 0) {
        html += `
            <div class="feedback-section">
                <h3>Detailed Agent Feedback</h3>
                <div class="raw-feedback">
        `;
        
        evaluation.raw_feedback.forEach(item => {
            html += `
                <div class="feedback-item ${item.category}">
                    <div class="feedback-category">${item.category}</div>
                    <p>${item.text}</p>
                </div>
            `;
        });
        
        html += `</div></div>`;
    }
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').style.display = 'none';
}

function continueToNextStep() {
    closeFeedbackModal();
    
    // Navigate to next step
    switch (currentSession.nextStep) {
        case 'assessment':
            showAssessmentStep();
            break;
        case 'cleaning':
            showCleaningStep();
            break;
        case 'dressing':
            showDressingStep();
            break;
        case 'completed':
            showCompletionScreen();
            break;
        default:
            console.error('Unknown next step:', currentSession.nextStep);
    }
}

// ==========================================
// Completion Screen
// ==========================================

function showCompletionScreen() {
    currentSession.currentStep = 'completed'; // Update session state
    showScreen('completionScreen');
    document.getElementById('currentStep').textContent = 'completed';
    
    const summary = document.getElementById('completionSummary');
    summary.innerHTML = `
        <h3>Session Summary</h3>
        <p><strong>Session ID:</strong> ${currentSession.sessionId}</p>
        <p><strong>Scenario:</strong> ${currentSession.scenarioMetadata.title}</p>
        <p>All procedural steps have been completed successfully!</p>
    `;
}

// ==========================================
// Initialize
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('VR Nursing Education System - Test UI Loaded');
    showScreen('startScreen');
});
