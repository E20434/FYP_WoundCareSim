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
    actionCounter: 0
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
    currentSession.currentStep = 'history';
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
    currentSession.currentStep = 'assessment';
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
        
        // Update UI with immediate feedback
        const statusBadge = document.getElementById(`status-${questionId}`);
        const feedbackDiv = document.getElementById(`feedback-${questionId}`);
        const optionsDiv = document.getElementById(`options-${questionId}`);
        
        // Show status
        statusBadge.style.display = 'inline-block';
        statusBadge.className = `mcq-status ${response.status}`;
        statusBadge.textContent = response.is_correct ? '✓ Correct' : '✗ Incorrect';
        
        // Show explanation
        feedbackDiv.style.display = 'block';
        feedbackDiv.className = `mcq-feedback ${response.status}`;
        feedbackDiv.innerHTML = `<strong>Explanation:</strong> ${response.explanation}`;
        
        // Disable options
        optionsDiv.style.pointerEvents = 'none';
        optionsDiv.style.opacity = '0.6';
        
    } catch (error) {
        console.error('Failed to submit MCQ answer:', error);
    }
}

// ==========================================
// CLEANING AND DRESSING Step (Combined - 9 Actions)
// ==========================================

function showCleaningAndDressingStep() {
    currentSession.currentStep = 'cleaning_and_dressing';
    currentSession.actionCounter = 0;
    showScreen('cleaningAndDressingScreen');
    document.getElementById('currentStep').textContent = 'cleaning_and_dressing';
    
    // Reset counter
    document.getElementById('actionCounter').textContent = '0';
    
    // Load action buttons
    loadCleaningAndDressingActions();
    
    // Clear feedback
    const feedbackBox = document.getElementById('realtimeFeedback');
    feedbackBox.innerHTML = '<strong>Real-Time Feedback:</strong><p class="text-muted">Perform actions to receive feedback...</p>';
}

function loadCleaningAndDressingActions() {
    const actions = [
        { type: 'action_initial_hand_hygiene', label: '1. Initial Hand Hygiene' },
        { type: 'action_clean_trolley', label: '2. Clean Dressing Trolley' },
        { type: 'action_hand_hygiene_after_cleaning', label: '3. Hand Hygiene After Cleaning' },
        { type: 'action_select_solution', label: '4. Select Cleaning Solution' },
        // Action 5 is verification - handled by form
        { type: 'action_select_dressing', label: '6. Select Dressing Materials' },
        // Action 7 is verification - handled by form
        { type: 'action_arrange_materials', label: '8. Arrange Materials on Trolley' },
        { type: 'action_bring_trolley', label: '9. Bring Trolley to Patient' }
    ];
    
    const container = document.getElementById('cleaningAndDressingActions');
    container.innerHTML = '';
    
    actions.forEach(action => {
        const button = document.createElement('button');
        button.className = 'action-btn';
        button.onclick = () => recordAction(action.type);
        button.innerHTML = `
            <span class="checkmark">✓</span>
            <span>${action.label}</span>
        `;
        container.appendChild(button);
    });
}

async function recordAction(actionType) {
    try {
        const response = await apiCall('/session/action', 'POST', {
            session_id: currentSession.sessionId,
            action_type: actionType
        });
        
        // Update counter
        currentSession.actionCounter++;
        document.getElementById('actionCounter').textContent = currentSession.actionCounter;
        
        // Display real-time feedback
        displayRealtimeFeedback(response.feedback);
        
    } catch (error) {
        console.error('Failed to record action:', error);
    }
}

async function verifySolution() {
    const solutionType = document.getElementById('solutionType').value.trim();
    const expiryDate = document.getElementById('solutionExpiry').value.trim();
    const packageCondition = document.getElementById('solutionCondition').value;
    
    if (!solutionType || !expiryDate) {
        showError('Please fill in all solution verification fields');
        return;
    }
    
    try {
        const response = await apiCall('/session/verify-material', 'POST', {
            session_id: currentSession.sessionId,
            material_type: 'solution',
            material_name: solutionType,
            expiry_date: expiryDate,
            package_condition: packageCondition
        });
        
        // Update counter (this is Action 5)
        currentSession.actionCounter++;
        document.getElementById('actionCounter').textContent = currentSession.actionCounter;
        
        // Display nurse response
        const responseDiv = document.getElementById('staffNurseCleaningAndDressing');
        responseDiv.innerHTML = `
            <div class="verification-response">
                <strong>Staff Nurse (Verification):</strong>
                <p>${response.nurse_response}</p>
            </div>
        `;
        
        // Display real-time feedback
        displayRealtimeFeedback(response.feedback);
        
        // Clear form
        document.getElementById('solutionType').value = '';
        document.getElementById('solutionExpiry').value = '';
        
    } catch (error) {
        console.error('Failed to verify solution:', error);
    }
}

async function verifyDressing() {
    const dressingType = document.getElementById('dressingType').value.trim();
    const expiryDate = document.getElementById('dressingExpiry').value.trim();
    const packageCondition = document.getElementById('dressingCondition').value;
    
    if (!dressingType || !expiryDate) {
        showError('Please fill in all dressing verification fields');
        return;
    }
    
    try {
        const response = await apiCall('/session/verify-material', 'POST', {
            session_id: currentSession.sessionId,
            material_type: 'dressing',
            material_name: dressingType,
            expiry_date: expiryDate,
            package_condition: packageCondition
        });
        
        // Update counter (this is Action 7)
        currentSession.actionCounter++;
        document.getElementById('actionCounter').textContent = currentSession.actionCounter;
        
        // Display nurse response
        const responseDiv = document.getElementById('staffNurseCleaningAndDressing');
        responseDiv.innerHTML = `
            <div class="verification-response">
                <strong>Staff Nurse (Verification):</strong>
                <p>${response.nurse_response}</p>
            </div>
        `;
        
        // Display real-time feedback
        displayRealtimeFeedback(response.feedback);
        
        // Clear form
        document.getElementById('dressingType').value = '';
        document.getElementById('dressingExpiry').value = '';
        
    } catch (error) {
        console.error('Failed to verify dressing:', error);
    }
}

function displayRealtimeFeedback(feedback) {
    const feedbackBox = document.getElementById('realtimeFeedback');
    
    let statusClass = feedback.status === 'complete' ? 'success' : 'warning';
    let statusIcon = feedback.status === 'complete' ? '✓' : '⚠️';
    
    let html = `
        <strong>Real-Time Feedback:</strong>
        <div class="feedback-message ${statusClass}">
            <span class="feedback-icon">${statusIcon}</span>
            <p>${feedback.message}</p>
    `;
    
    // Show missing actions if any
    if (feedback.missing_actions && feedback.missing_actions.length > 0) {
        html += `
            <div class="missing-actions">
                <strong>Missing Prerequisites:</strong>
                <ul>
                    ${feedback.missing_actions.map(action => `
                        <li>${action.replace('action_', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }
    
    html += '</div>';
    feedbackBox.innerHTML = html;
}

// ==========================================
// Staff Nurse
// ==========================================

async function askStaffNurse() {
    const step = currentSession.currentStep;
    let inputId, responseId;
    
    // Determine input/response IDs based on step
    if (step === 'history') {
        inputId = 'nurseQuestionHistory';
        responseId = 'staffNurseHistory';
    } else if (step === 'assessment') {
        inputId = 'nurseQuestionAssessment';
        responseId = 'staffNurseAssessment';
    } else if (step === 'cleaning_and_dressing') {
        inputId = 'nurseQuestionCleaningAndDressing';
        responseId = 'staffNurseCleaningAndDressing';
    }
    
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
            <strong>Staff Nurse (Guidance):</strong>
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
        
        // Display appropriate feedback/results
        if (step === 'history') {
            // History: Show narrated feedback + score
            displayHistoryFeedback(response.feedback);
        } else if (step === 'assessment') {
            // Assessment: Show MCQ results only (no narration)
            displayAssessmentResults(response.mcq_result);
        } else if (step === 'cleaning_and_dressing') {
            // Cleaning & Dressing: Show summary only (no scores/narration)
            displayPreparationSummary(response.summary);
        }
        
    } catch (error) {
        console.error('Failed to finish step:', error);
    }
}

function displayHistoryFeedback(feedback) {
    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    
    let html = `
        <div class="feedback-section">
            <h3>📋 History Taking Feedback</h3>
    `;
    
    // Narrated feedback (primary)
    if (feedback.narrated_feedback) {
        html += `
            <div class="narrated-feedback">
                ${feedback.narrated_feedback.message_text}
            </div>
        `;
    }
    
    // Score display
    if (feedback.score !== undefined) {
        const scorePercent = (feedback.score * 100).toFixed(0);
        html += `
            <div class="score-display">
                <div class="score-label">Step Quality Score</div>
                <div class="score-value">${feedback.score.toFixed(2)}</div>
                <div class="score-bar">
                    <div class="score-fill" style="width: ${scorePercent}%"></div>
                </div>
                <div class="score-interpretation">${feedback.interpretation || ''}</div>
            </div>
        `;
    }
    
    html += '</div>';
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function displayAssessmentResults(mcqResult) {
    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    
    const scorePercent = (mcqResult.score * 100).toFixed(0);
    
    let html = `
        <div class="feedback-section">
            <h3>📊 Assessment Results</h3>
            <div class="mcq-summary">
                <div class="mcq-score-large">
                    ${mcqResult.correct_count} / ${mcqResult.total_questions}
                </div>
                <div class="mcq-summary-text">
                    ${mcqResult.summary}
                </div>
                <div class="score-bar">
                    <div class="score-fill" style="width: ${scorePercent}%"></div>
                </div>
            </div>
    `;
    
    // Note: No narrated feedback for assessment - MCQ explanations already provided
    html += `
            <div class="info-box">
                <strong>ℹ️ Note:</strong> Detailed explanations were provided for each question during the assessment.
            </div>
        </div>
    `;
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function displayPreparationSummary(summary) {
    const modal = document.getElementById('feedbackModal');
    const content = document.getElementById('feedbackContent');
    
    let html = `
        <div class="feedback-section">
            <h3>🔧 Preparation Summary</h3>
            <div class="preparation-summary">
                <p>${summary.message}</p>
                <div class="action-count">
                    <strong>Actions Completed:</strong> ${summary.actions_completed} / ${summary.expected_actions}
                </div>
            </div>
            <div class="info-box">
                <strong>ℹ️ Note:</strong> Real-time feedback was provided during preparation. No final score is given for this step.
            </div>
        </div>
    `;
    
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
        case 'cleaning_and_dressing':
            showCleaningAndDressingStep();
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
    currentSession.currentStep = 'completed';
    showScreen('completionScreen');
    document.getElementById('currentStep').textContent = 'completed';
    
    const summary = document.getElementById('completionSummary');
    summary.innerHTML = `
        <h3>Session Summary</h3>
        <p><strong>Session ID:</strong> ${currentSession.sessionId}</p>
        <p><strong>Scenario:</strong> ${currentSession.scenarioMetadata.title}</p>
        <div class="completion-message">
            <p>✓ Patient History Completed</p>
            <p>✓ Wound Assessment Completed</p>
            <p>✓ Cleaning & Dressing Preparation Completed</p>
        </div>
        <p class="success-message">All procedural steps have been completed successfully!</p>
    `;
}

// ==========================================
// Initialize
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('VR Nursing Education System - Test UI Loaded (Updated)');
    showScreen('startScreen');
});
