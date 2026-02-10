let isTyping = false;

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const msg = input.value.trim();
    if (!msg) return;
    
    addMessage(msg, 'user');
    input.value = '';
    
    const typingMsg = addMessage('Typing...', 'bot', 'typing');
    
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: msg})
        });
        
        if (!res.ok) throw new Error('Server error');
        const data = await res.json();
        
        document.getElementById('messages').removeChild(typingMsg);
        
        let type = 'bot-message';
        if (data.type === 'conflict' || data.error) type += ' conflict';
        else if (data.type === 'success') type += ' success';
        else if (data.type === 'urgent') type += ' urgent';
        
        addMessage(data.content || data.error || 'No response', 'bot', type);
        
        if (data.pilots_html) document.getElementById('pilotTable').innerHTML = data.pilots_html;
        if (data.drones_html) document.getElementById('droneTable').innerHTML = data.drones_html;
        
    } catch (e) {
        document.getElementById('messages').removeChild(typingMsg);
        addMessage('❌ Backend error. Check terminal & Google Sheets permissions.', 'bot', 'conflict');
        document.getElementById('connectionStatus').textContent = '● Offline';
        document.getElementById('connectionStatus').className = 'status-dot offline';
    }
}

function addMessage(text, sender, extraClass = '') {
    const messages = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `message ${sender}-message ${extraClass}`;
    div.innerHTML = text.replace(/\n/g, '<br>');
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

function quick(query) {
    document.getElementById('messageInput').value = query;
    sendMessage();
}

function toggleData() {
    const tables = document.getElementById('dataTables');
    tables.classList.toggle('hidden');
}

document.getElementById('sendBtn').onclick = sendMessage;
document.getElementById('messageInput').onkeypress = (e) => e.key === 'Enter' && sendMessage();

// Live status polling
async function updateStatus() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();
        document.getElementById('pilotCount').textContent = data.pilots;
        document.getElementById('droneCount').textContent = data.drones;
        document.getElementById('connectionStatus').textContent = '● Live';
        document.getElementById('connectionStatus').className = 'status-dot online';
    } catch {
        document.getElementById('connectionStatus').textContent = '● Offline';
        document.getElementById('connectionStatus').className = 'status-dot offline';
    }
}
setInterval(updateStatus, 5000);
updateStatus(); // Initial load

// Welcome message
addMessage(`Hello! Connected to your sheets (Pilots: Bangalore/Mumbai data loaded). Try "available pilots in Bangalore", "fleet status", "conflicts", or "urgent reassign".`, 'bot');

// In your chat response handler, add:
if (data.ai_analysis) {
    const analysis = data.ai_analysis;
    let decisionHtml = `
        <div class="decision-panel">
            <h4>🤖 AI Decision Support (${analysis.confidence} Confidence)</h4>
            
            <div class="decision-section">
                <h5>📊 Analysis</h5>
                <p>${analysis.analysis}</p>
            </div>
            
            <div class="decision-section">
                <h5>💡 Recommendation</h5>
                <p class="confidence-${analysis.confidence.toLowerCase()}">${analysis.recommendation}</p>
            </div>
            
            <div class="decision-section">
                <h5>✅ Suggested Actions</h5>
                <ul class="action-list">
                    ${analysis.actions.map(a => `<li>${a}</li>`).join('')}
                </ul>
            </div>
            
            ${analysis.risks.length ? `
            <div class="decision-section">
                <h5>⚠️ Risks</h5>
                <ul class="risk-list">
                    ${analysis.risks.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>` : ''}
        </div>
    `;
    // Append to message
    addMessage(decisionHtml, 'bot');
}