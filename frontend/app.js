// DOM Elements
const form = document.getElementById('investigation-form');
const submitBtn = document.getElementById('submit-btn');
const queryInput = document.getElementById('query');
const modelSelect = document.getElementById('model');

const progressSection = document.getElementById('progress-section');
const statusText = document.getElementById('status-text');
const errorContainer = document.getElementById('error-container');

const resultsSection = document.getElementById('results-section');
const summaryContent = document.getElementById('summary-content');
const searchResultsContent = document.getElementById('search-results-content');
const searchCount = document.getElementById('search-count');
const scrapedContentList = document.getElementById('scraped-content-list');
const scrapeCount = document.getElementById('scrape-count');
const enrichmentDataContent = document.getElementById('enrichment-data-content');
const enrichmentCount = document.getElementById('enrichment-count');

const pivotsCard = document.getElementById('pivots-card');
const pivotsContent = document.getElementById('pivots-content');

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatHistory = document.getElementById('chat-history');
const chatBtn = document.getElementById('chat-btn');

let currentJobId = null;
let pollInterval = null;

// Handle Form Submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const query = queryInput.value.trim();
    const model = modelSelect.value;
    
    if (!query) return;

    // Reset UI
    errorContainer.classList.add('hidden');
    resultsSection.classList.add('hidden');
    progressSection.classList.remove('hidden');
    submitBtn.disabled = true;
    statusText.textContent = "Initializing Investigation...";
    
    try {
        const response = await api.startInvestigation(query, model);
        currentJobId = response.job_id;
        startPolling(currentJobId);
    } catch (err) {
        showError(err.message);
        submitBtn.disabled = false;
        progressSection.classList.add('hidden');
    }
});

// Polling Logic
function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);
    
    // Poll every 2 seconds
    pollInterval = setInterval(async () => {
        try {
            const data = await api.getInvestigation(jobId);
            
            if (data.status === 'failed') {
                stopPolling();
                showError(data.error || "Investigation failed internally.");
                submitBtn.disabled = false;
                progressSection.classList.add('hidden');
                return;
            }
            
            if (data.status === 'completed') {
                stopPolling();
                submitBtn.disabled = false;
                progressSection.classList.add('hidden');
                renderResults(data);
                return;
            }
            
            // Still running
            statusText.textContent = getStageText(data.stage);
            
        } catch (err) {
            stopPolling();
            showError(`Polling error: ${err.message}`);
            submitBtn.disabled = false;
            progressSection.classList.add('hidden');
        }
    }, 2000);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function getStageText(stage) {
    const stages = {
        'pending': 'Queued...',
        'loading_llm': 'Loading AI model...',
        'refining_query': 'Refining search query...',
        'searching': 'Searching the dark web...',
        'filtering': 'Filtering search results...',
        'scraping': 'Scraping target pages...',
        'enriching': 'Running OSINT enrichment...',
        'summarizing': 'Generating summary...',
        'pivoting': 'Suggesting follow-up pivots...',
        'done': 'Finishing up...'
    };
    return stages[stage] || `Processing (${stage})...`;
}

function showError(msg) {
    errorContainer.textContent = msg;
    errorContainer.classList.remove('hidden');
}

// Render Results
function renderResults(data) {
    resultsSection.classList.remove('hidden');
    
    // Summary
    summaryContent.innerHTML = renderMarkdown(data.summary || "No summary generated.");
    
    // Search Results
    const sr = data.search_results || [];
    searchCount.textContent = sr.length;
    searchResultsContent.innerHTML = sr.map(r => `
        <div style="margin-bottom: 0.5rem">
            <strong>${escapeHtml(r.title)}</strong><br>
            <a href="${escapeHtml(r.link)}" target="_blank" style="color: var(--primary)">${escapeHtml(r.link)}</a>
        </div>
    `).join('') || 'None';

    // Scraped Data
    const sc = data.scraped_data || [];
    scrapeCount.textContent = sc.length;
    scrapedContentList.innerHTML = sc.map(s => `
        <details style="margin-bottom: 0.5rem; background: rgba(0,0,0,0.2); padding: 0.5rem; border-radius: 4px;">
            <summary style="cursor: pointer; font-weight: bold;">${escapeHtml(s.url)}</summary>
            <pre style="margin-top: 0.5rem; font-size: 0.8rem; white-space: pre-wrap;">${escapeHtml(s.content)}</pre>
        </details>
    `).join('') || 'None';

    // Enrichment Data
    const en = data.enrichment_data || [];
    enrichmentCount.textContent = en.length;
    enrichmentDataContent.innerHTML = en.map(e => `
        <details style="margin-bottom: 0.5rem; background: rgba(0,0,0,0.2); padding: 0.5rem; border-radius: 4px;">
            <summary style="cursor: pointer; font-weight: bold;">
                ${escapeHtml(e.indicator)} <span class="badge" style="float:right">${escapeHtml(e.provider)}</span>
            </summary>
            <div style="margin-top: 0.5rem; font-size: 0.85rem;">
                <strong>Status:</strong> ${escapeHtml(e.status)}<br>
                <strong>Type:</strong> ${escapeHtml(e.indicator_type)}<br>
                <pre style="margin-top: 0.5rem; font-size: 0.8rem; white-space: pre-wrap;">${escapeHtml(JSON.stringify(e.data, null, 2))}</pre>
            </div>
        </details>
    `).join('') || 'None';

    // Pivots
    const pv = data.pivots || [];
    if (pv.length > 0) {
        pivotsCard.classList.remove('hidden');
        pivotsContent.innerHTML = pv.map(p => `
            <button class="pivot-btn" onclick="applyPivot('${escapeHtml(p)}')">${escapeHtml(p)}</button>
        `).join('');
    } else {
        pivotsCard.classList.add('hidden');
    }

    // Reset Chat
    chatHistory.innerHTML = '';
}

window.applyPivot = function(query) {
    queryInput.value = query;
    window.scrollTo({ top: 0, behavior: 'smooth' });
};

// Handle Chat
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentJobId) return;
    
    const question = chatInput.value.trim();
    if (!question) return;
    
    // Add User Message
    addChatMessage('user', question);
    chatInput.value = '';
    chatBtn.disabled = true;
    
    try {
        const model = modelSelect.value;
        const response = await api.chat(currentJobId, question, model);
        addChatMessage('assistant', response.answer);
    } catch (err) {
        addChatMessage('assistant', `⚠️ Error: ${err.message}`);
    } finally {
        chatBtn.disabled = false;
    }
});

function addChatMessage(role, content) {
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = renderMarkdown(content);
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Basic markdown/HTML escaper (simple approach to avoid bringing in a heavy markdown lib)
function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function renderMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Newlines
    html = html.replace(/\n/g, '<br>');
    return html;
}
