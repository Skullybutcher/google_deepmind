# 🎨 Person C — Frontend Swarm Handover

> **How to use this file**: You are Person C. This file contains EVERYTHING you need to build your part.
> 1. Read `AGENTS.md` first for project-wide coding standards and the SSE event format.
> 2. Read THIS file for your exact tasks, deliverables, and timeline.
> 3. Paste `AGENTS.md` + this file as context into your AI coding agents.
> 4. You can run multiple agents in parallel — e.g., one builds CSS while another builds JS.
>    They MUST all target the same three files: `index.html`, `style.css`, `app.js`.

---

## Your Role

**Frontend Swarm Lead** — You own the entire web dashboard, SSE consumption, visual design (glassmorphism, typography, layout), and the demo recording. Your UI is the **primary thing judges see** — it must make the multi-agent orchestration *visible and impressive*.

---

## Your Files (You Create These)

| File | Purpose | Priority |
|---|---|---|
| `frontend/index.html` | Single-page dashboard — all structure | P0 |
| `frontend/style.css` | All styles — glassmorphism, layout, typography, animations | P0 |
| `frontend/app.js` | SSE handling, DOM updates, button handlers, state rendering | P0 |
| `frontend/mock_events.json` | Pre-recorded SSE events for testing without backend | P1 |

---

## Design Requirements (Priority Ordered)

Build in this exact order. If time runs short, cut from the bottom.

### P0 — Must Ship (1h 15min total)

1. **Glassmorphism main card** (20 min)
   - Central panel: `backdrop-filter: blur(16px)`, `background: rgba(255,255,255,0.7)`
   - `border-radius: 24px`, `border: 1px solid rgba(255,255,255,0.3)`
   - Subtle `box-shadow: 0 8px 32px rgba(0,0,0,0.1)`

2. **Soft gradient background** (5 min)
   - `background: linear-gradient(135deg, #e0f2e9 0%, #f0f4f8 50%, #e8edf2 100%)`
   - Mint/gray palette — calm, not stark white

3. **Typography** (5 min)
   - Google Fonts: `Playfair Display` (headline, italic) + `Inter` (body)
   - `<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">`

4. **Agent status panel** (30 min)
   - Inside the glass card: 5 rows, one per agent
   - Each row: agent name | role description | status chip
   - Status chips: ⏳ `PENDING` (gray) → 🔄 `IN_PROGRESS` (blue pulse) → ✅ `COMPLETED` (green) → ❌ `FAILED` (red)
   - Current status visible at a glance

5. **Primary CTA: "Trigger Incident"** (10 min)
   - Solid pill button, high contrast: `background: #1a1a2e`, `color: white`, `border-radius: 50px`
   - Large, centered above or inside the glass card
   - Only ONE primary button at a time — this is it

6. **SSE integration** (30 min)
   - `EventSource` connecting to `/api/events`
   - Parse each event, update agent status chips
   - Update incident status badge at top of card

### P1 — Should Ship (45 min total)

7. **Failure injection buttons** (15 min)
   - "Inject: Log Failure" + "Inject: Remediation Failure"
   - Outline style (not solid): `border: 1px solid #666`, `background: transparent`
   - Visually deemphasized — must NOT compete with primary CTA

8. **Incident timeline** (30 min)
   - Scrollable list below the main glass card
   - Each entry: timestamp | event type badge (color-coded) | detail text
   - Auto-scroll to latest event
   - Shows the full `history` array from state

### P2 — Nice to Have (40 min total)

9. **Tech credibility strip** (10 min)
   - Below the glass card: "Powered by Antigravity Agent · Interactions API · FastAPI · SSE"
   - Small text, muted color, centered

10. **Floating agent avatars** (30 min)
    - Small cards positioned around the main glass panel with `position: absolute`
    - Each shows: emoji icon + agent name + current status
    - Varying sizes and slight rotation for depth effect
    - `border-radius: 16px`, semi-transparent backgrounds

### P3 — Bonus Polish (30 min total)

11. **Micro-animations** (15 min)
    - Status chip transitions: `transition: all 0.3s ease`
    - New timeline entries: `@keyframes fadeSlideIn { from { opacity: 0; transform: translateY(10px) } }`
    - Primary CTA hover: subtle scale + shadow increase

12. **Loading state** (5 min)
    - Pulsing dot animation while agents are working

13. **Responsive check** (10 min)
    - Works on 1280px+ screens (demo will be on a desktop)
    - No need for mobile — judges evaluate on desktop

---

## Hour-by-Hour Tasks

### Hour 0:00–0:45 — HTML Scaffold + Design System

**Goal**: `index.html` loads with beautiful glassmorphism card, gradient background, fonts, and placeholder content.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEGIS — Autonomous Incident Response</title>
    <meta name="description" content="Multi-agent incident response system powered by Antigravity Agent">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="background-gradient"></div>
    
    <main class="container">
        <header class="hero">
            <h1 class="title"><em>AEGIS</em></h1>
            <p class="subtitle">Autonomous Emergency Grid for Incident Self-healing</p>
        </header>

        <div class="glass-card" id="main-panel">
            <div class="incident-header" id="incident-header">
                <span class="status-badge" id="incident-status">ALL SYSTEMS NORMAL</span>
            </div>

            <div class="agent-panel" id="agent-panel">
                <!-- Agent rows rendered by JS -->
            </div>

            <div class="cta-container">
                <button class="btn-primary" id="btn-trigger" onclick="triggerIncident()">
                    Trigger Incident
                </button>
            </div>

            <div class="failure-buttons" id="failure-buttons" style="display:none;">
                <button class="btn-secondary" id="btn-inject-log" onclick="injectFailure('LOG_SOURCE_UNAVAILABLE')">
                    Inject: Log Failure
                </button>
                <button class="btn-secondary" id="btn-inject-remed" onclick="injectFailure('REMEDIATION_FAILED')">
                    Inject: Remediation Failure
                </button>
            </div>
        </div>

        <div class="timeline-container" id="timeline-container">
            <h3 class="timeline-title">Incident Timeline</h3>
            <div class="timeline" id="timeline">
                <!-- Timeline entries rendered by JS -->
            </div>
        </div>

        <div class="credibility-strip">
            Powered by <strong>Antigravity Agent</strong> · Interactions API · FastAPI · SSE
        </div>
    </main>

    <script src="app.js"></script>
</body>
</html>
```

**Key CSS patterns** (`style.css`):
```css
/* === DESIGN TOKENS === */
:root {
    --bg-gradient-start: #e0f2e9;
    --bg-gradient-mid: #f0f4f8;
    --bg-gradient-end: #e8edf2;
    --glass-bg: rgba(255, 255, 255, 0.7);
    --glass-border: rgba(255, 255, 255, 0.3);
    --glass-blur: 16px;
    --glass-radius: 24px;
    --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    --font-display: 'Playfair Display', serif;
    --font-body: 'Inter', sans-serif;
    --color-primary: #1a1a2e;
    --color-success: #10b981;
    --color-error: #ef4444;
    --color-warning: #f59e0b;
    --color-info: #3b82f6;
    --color-pending: #9ca3af;
    --color-text: #1f2937;
    --color-text-muted: #6b7280;
    --radius-pill: 50px;
    --radius-chip: 8px;
}

body {
    margin: 0;
    font-family: var(--font-body);
    color: var(--color-text);
    min-height: 100vh;
    background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-mid) 50%, var(--bg-gradient-end) 100%);
}

.glass-card {
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--glass-radius);
    box-shadow: var(--glass-shadow);
    padding: 2rem 2.5rem;
    max-width: 800px;
    margin: 0 auto;
}

h1.title {
    font-family: var(--font-display);
    font-size: 3rem;
    text-align: center;
    margin-bottom: 0.25rem;
}

.btn-primary {
    background: var(--color-primary);
    color: white;
    border: none;
    border-radius: var(--radius-pill);
    padding: 14px 40px;
    font-family: var(--font-body);
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}
.btn-primary:hover {
    transform: scale(1.03);
    box-shadow: 0 4px 20px rgba(26, 26, 46, 0.3);
}

.btn-secondary {
    background: transparent;
    border: 1px solid var(--color-text-muted);
    border-radius: var(--radius-pill);
    padding: 8px 20px;
    font-family: var(--font-body);
    font-size: 0.85rem;
    color: var(--color-text-muted);
    cursor: pointer;
}
```

### Hour 0:45–1:30 — Agent Status Panel

Render 5 agent rows inside the glass card. Use mock data first:

```javascript
// app.js
const AGENTS = [
    { id: 'Planner', name: 'Planner', role: 'Decomposes alert into subtasks', icon: '🧠' },
    { id: 'LogAnalyzer', name: 'Log Analyzer', role: 'Scans application logs', icon: '📋' },
    { id: 'MetricsAgent', name: 'Metrics Agent', role: 'Analyzes infrastructure metrics', icon: '📊' },
    { id: 'Diagnostician', name: 'Diagnostician', role: 'Correlates findings', icon: '🔬' },
    { id: 'Remediator', name: 'Remediator', role: 'Executes fixes', icon: '🔧' }
];

function renderAgentPanel(steps) {
    const panel = document.getElementById('agent-panel');
    panel.innerHTML = AGENTS.map(agent => {
        const step = steps?.find(s => s.agent === agent.id);
        const status = step?.status || 'IDLE';
        return `
            <div class="agent-row">
                <span class="agent-icon">${agent.icon}</span>
                <div class="agent-info">
                    <span class="agent-name">${agent.name}</span>
                    <span class="agent-role">${agent.role}</span>
                </div>
                <span class="status-chip status-${status.toLowerCase()}">${status}</span>
            </div>
        `;
    }).join('');
}
```

### Hour 1:30–2:00 — CTA Buttons + Failure Injection UI

- "Trigger Incident" → `POST /api/trigger-incident`
- "Inject: Log Failure" → `POST /api/inject-failure` with `{"failure_type": "LOG_SOURCE_UNAVAILABLE"}`
- "Inject: Remediation Failure" → `POST /api/inject-failure` with `{"failure_type": "REMEDIATION_FAILED"}`
- Show failure buttons ONLY after an incident is triggered

```javascript
const API_BASE = ''; // Same origin, or set to deployed backend URL

async function triggerIncident() {
    const btn = document.getElementById('btn-trigger');
    btn.disabled = true;
    btn.textContent = 'Starting...';
    
    await fetch(`${API_BASE}/api/trigger-incident`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            alert_type: 'HIGH_LATENCY',
            service: 'api-gateway',
            severity: 'P1'
        })
    });
    
    document.getElementById('failure-buttons').style.display = 'flex';
    connectSSE();
}

async function injectFailure(failureType) {
    await fetch(`${API_BASE}/api/inject-failure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ failure_type: failureType })
    });
}
```

### Hour 2:00–2:30 — SSE Integration

```javascript
function connectSSE() {
    const source = new EventSource(`${API_BASE}/api/events`);
    
    source.addEventListener('state_update', (e) => {
        const event = JSON.parse(e.data);
        handleEvent(event);
    });
    
    source.onerror = () => {
        console.warn('SSE connection lost, retrying...');
        // EventSource auto-reconnects
    };
}

function handleEvent(event) {
    // Update incident status badge
    const statusBadge = document.getElementById('incident-status');
    statusBadge.textContent = event.data.status;
    statusBadge.className = `status-badge status-${event.data.status.toLowerCase()}`;
    
    // Update agent panel
    if (event.data.steps) {
        renderAgentPanel(event.data.steps);
    }
    
    // Add to timeline
    addTimelineEntry(event);
    
    // Update message
    if (event.data.message) {
        document.getElementById('current-message')?.textContent = event.data.message;
    }
}
```

### Hour 2:30–3:00 — Incident Timeline

```javascript
function addTimelineEntry(event) {
    const timeline = document.getElementById('timeline');
    const entry = document.createElement('div');
    entry.className = 'timeline-entry fade-in';
    
    const time = new Date(event.timestamp).toLocaleTimeString();
    const typeClass = getEventTypeClass(event.event_type);
    
    entry.innerHTML = `
        <span class="timeline-time">${time}</span>
        <span class="timeline-badge ${typeClass}">${event.event_type}</span>
        <span class="timeline-detail">${event.data.message || ''}</span>
    `;
    
    timeline.appendChild(entry);
    timeline.scrollTop = timeline.scrollHeight; // Auto-scroll
}

function getEventTypeClass(type) {
    const map = {
        'INCIDENT_CREATED': 'badge-info',
        'PLAN_CREATED': 'badge-info',
        'AGENT_STARTED': 'badge-info',
        'AGENT_COMPLETED': 'badge-success',
        'AGENT_FAILED': 'badge-error',
        'REPLAN_TRIGGERED': 'badge-warning',
        'PLAN_UPDATED': 'badge-warning',
        'RESOLVED': 'badge-success',
        'ESCALATED': 'badge-error'
    };
    return map[type] || 'badge-info';
}
```

### Hour 3:00–3:30 — Floating Avatars (If Time)

Absolute-positioned small cards around the glass panel. Skip if behind schedule.

### Hour 3:30–4:00 — Integration + Polish

- [ ] Verify `API_BASE` is empty string (same-origin via Firebase rewrite)
- [ ] Test full happy path through live backend
- [ ] Test both failure scenarios
- [ ] Fix any text overflow from real agent outputs (add `overflow: hidden; text-overflow: ellipsis`)
- [ ] Check that status chips animate on change
- [ ] Check timeline auto-scrolls

### Hour 4:00–4:30 — Demo Recording

- [ ] Open the deployed app in Chrome (`your-project.web.app`)
- [ ] Start screen recording (OBS / browser extension)
- [ ] Record: happy path (40 seconds)
- [ ] Record: failure 1 → recovery (30 seconds)
- [ ] Record: failure 2 → escalation (30 seconds)
- [ ] Narrate or add captions (optional)
- [ ] Upload to YouTube (unlisted)
- [ ] Share link with Person B for writeup

---

## Mock Data for Testing Without Backend

Create `frontend/mock_events.json` for standalone testing:

```json
[
    {"delay": 500, "event_type": "INCIDENT_CREATED", "timestamp": "2026-09-26T10:00:00Z", "data": {"status": "PLANNING", "steps": [], "history": [], "message": "Incident created: High Latency on api-gateway"}},
    {"delay": 2000, "event_type": "PLAN_CREATED", "timestamp": "2026-09-26T10:00:02Z", "data": {"status": "INVESTIGATING", "steps": [{"id": "S1", "agent": "LogAnalyzer", "status": "PENDING", "description": "Analyze logs"}, {"id": "S2", "agent": "MetricsAgent", "status": "PENDING", "description": "Check metrics"}], "history": [{"event": "PLAN_CREATED"}], "message": "Plan created with 4 steps"}},
    {"delay": 1500, "event_type": "AGENT_STARTED", "timestamp": "2026-09-26T10:00:04Z", "data": {"status": "INVESTIGATING", "active_agent": "LogAnalyzer", "steps": [{"id": "S1", "agent": "LogAnalyzer", "status": "IN_PROGRESS"}, {"id": "S2", "agent": "MetricsAgent", "status": "IN_PROGRESS"}], "message": "LogAnalyzer and MetricsAgent running in parallel..."}},
    {"delay": 3000, "event_type": "AGENT_COMPLETED", "timestamp": "2026-09-26T10:00:07Z", "data": {"status": "INVESTIGATING", "steps": [{"id": "S1", "agent": "LogAnalyzer", "status": "COMPLETED"}, {"id": "S2", "agent": "MetricsAgent", "status": "COMPLETED"}], "message": "Both investigators completed. Anomalies detected."}},
    {"delay": 2000, "event_type": "AGENT_STARTED", "timestamp": "2026-09-26T10:00:09Z", "data": {"status": "DIAGNOSING", "active_agent": "Diagnostician", "message": "Diagnostician correlating findings..."}},
    {"delay": 3000, "event_type": "AGENT_COMPLETED", "timestamp": "2026-09-26T10:00:12Z", "data": {"status": "REMEDIATING", "active_agent": "Remediator", "message": "Root cause: Memory leak from deploy v2.3.1. Executing rollback..."}},
    {"delay": 2500, "event_type": "RESOLVED", "timestamp": "2026-09-26T10:00:15Z", "data": {"status": "RESOLVED", "message": "Incident RESOLVED. Rolled back to v2.3.0. All health checks passing."}}
]
```

**Replay mode** (use when backend is unavailable):
```javascript
async function replayMockEvents() {
    const events = await fetch('mock_events.json').then(r => r.json());
    for (const event of events) {
        await new Promise(resolve => setTimeout(resolve, event.delay));
        handleEvent(event);
    }
}
```

---

## What You Receive From Others

| From | What | When |
|---|---|---|
| Person A | SSE endpoint at `localhost:8000/api/events` | 1:30 |
| Person A | Mock SSE events for testing | 1:30 |
| Person A | Deployed Cloud Run URL (auto-proxied via Firebase rewrite) | 3:30 |

## What You Deliver To Others

| To | What | When |
|---|---|---|
| Person A | Frontend files for static serving | 3:30 |
| Person B | Demo video link (YouTube) | 4:15 |
| ALL | Working, polished dashboard | 3:30 |

---

## Descope Order (If Behind Schedule)

Cut from bottom of this list first:
1. ~~Micro-animations~~ (P3) — skip, everything still works
2. ~~Floating agent avatars~~ (P2) — skip, card is enough
3. ~~Credibility strip~~ (P2) — add as plain text in 2 minutes if time
4. ~~Incident timeline~~ (P1) — skip, just show current status in card
5. **NEVER CUT**: Glass card + agent panel + CTA buttons + SSE integration
