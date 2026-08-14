class ApiClient {
    constructor() {
        // Automatically determine the base URL
        // If served from FastAPI, it's the current origin.
        // If served locally via a static server while FastAPI is on 8000, fallback appropriately.
        this.baseUrl = window.location.origin;
        if (this.baseUrl.includes('5500') || this.baseUrl.includes('3000')) {
            // Local dev fallback
            this.baseUrl = 'http://localhost:8000';
        }
    }

    async health() {
        const res = await fetch(`${this.baseUrl}/api/health`);
        if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
        return res.json();
    }

    async startInvestigation(query, model) {
        const res = await fetch(`${this.baseUrl}/api/investigation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, model })
        });
        
        if (!res.ok) {
            const err = await res.text();
            throw new Error(`Failed to start investigation: ${err}`);
        }
        return res.json(); // { job_id: "...", status: "accepted" }
    }

    async getInvestigation(jobId) {
        const res = await fetch(`${this.baseUrl}/api/investigation/${jobId}`);
        if (!res.ok) {
            if (res.status === 404) throw new Error('Investigation not found');
            throw new Error(`Failed to poll investigation: ${res.statusText}`);
        }
        return res.json();
    }

    async chat(jobId, question, model) {
        const res = await fetch(`${this.baseUrl}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: jobId, question, model })
        });
        
        if (!res.ok) {
            const err = await res.text();
            throw new Error(`Chat request failed: ${err}`);
        }
        return res.json(); // { answer: "..." }
    }
}

const api = new ApiClient();
