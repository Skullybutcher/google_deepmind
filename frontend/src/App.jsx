import React, { useState, useEffect, useRef } from 'react';

const MOCK_MODE = false;
const API_BASE = import.meta.env.VITE_API_BASE || '';

const INITIAL_AGENTS = [
    { id: 'Planner', name: 'Planner', role: 'Decomposes alert into subtasks', icon: 'psychology' },
    { id: 'LogAnalyzer', name: 'Log Analyzer', role: 'Scans application logs', icon: 'article' },
    { id: 'MetricsAgent', name: 'Metrics Agent', role: 'Analyzes infrastructure metrics', icon: 'monitoring' },
    { id: 'Diagnostician', name: 'Diagnostician', role: 'Correlates findings', icon: 'troubleshoot' },
    { id: 'Remediator', name: 'Remediator', role: 'Executes fixes', icon: 'build' }
];

import LightRays from './components/LightRays';

function App() {
  const [incidentStatus, setIncidentStatus] = useState('ALL SYSTEMS NORMAL');
  const [steps, setSteps] = useState([]);
  const [history, setHistory] = useState([]);
  const [isTriggered, setIsTriggered] = useState(false);
  const [severity, setSeverity] = useState('P1');
  const [isApproving, setIsApproving] = useState(false);
  const [awaitingApproval, setAwaitingApproval] = useState(false);
  const [toasts, setToasts] = useState([]);
  const timelineRef = useRef(null);
  const sseRef = useRef(null);

  // Toast system for APPROVED / SPAWNED_AGENTS events
  const addToast = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  };

  useEffect(() => {
    // Auto-scroll disabled per user request
  }, [history]);

  // Close any existing SSE connection
  const closeSSE = () => {
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }
  };

  const handleEvent = (event) => {
    const data = event.data;
    if (data.status) setIncidentStatus(data.status);
    if (data.steps) setSteps(data.steps);

    // (OC) skip bare snapshot replays in the timeline — status/steps above
    // already update the UI from them.
    const isSnapshot = event.event_type === 'STATE_SNAPSHOT';

    // Handle AWAITING_APPROVAL status from SSE
    if (data.status === 'AWAITING_APPROVAL') {
      setAwaitingApproval(true);
      setIsTriggered(true);
    }
    if (data.status === 'RESOLVED' || data.status === 'ESCALATED') {
      setAwaitingApproval(false);
    }

    if (!isSnapshot) {
      setHistory(prev => [...prev, {
        id: Date.now() + Math.random(),
        timestamp: event.timestamp || new Date().toISOString(),
        event_type: event.event_type,
        message: data.message || ''
      }]);
    }

    // OC6b: Toast notifications for APPROVED and SPAWNED_AGENTS
    if (event.event_type === 'APPROVED') {
      addToast('✅ Fix approved — remediation resumed', 'success');
    }
    if (event.event_type === 'SPAWNED_AGENTS') {
      const agentNames = data.spawned_agents?.join(', ') || 'additional agents';
      addToast(`🔁 Scaling: spawned ${agentNames}`, 'info');
    }

    // Auto-unlock the trigger button when the pipeline reaches a terminal state
    const terminal = ['RESOLVED', 'ESCALATED'];
    if (terminal.includes(data.status) || terminal.includes(event.event_type)) {
      setIsTriggered(false);
      closeSSE();
    }
  };

  const triggerIncident = async () => {
    // Reset all UI state for a fresh run
    closeSSE();
    setSteps([]);
    setHistory([]);
    setIsTriggered(true);
    setIncidentStatus('STARTING...');
    setAwaitingApproval(false);
    if (MOCK_MODE) {
      // Mock mode logic omitted for brevity as API is used
    } else {
      try {
        // Clear any stale injected failures from previous sessions before
        // triggering so a fresh happy-path run is not polluted.
        await fetch(`${API_BASE}/api/inject-failure`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ failure_type: 'NONE' })
        });
        await fetch(`${API_BASE}/api/trigger-incident`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            alert_type: 'HIGH_LATENCY',
            service: 'api-gateway',
            severity: severity
          })
        });
        connectSSE();
      } catch (err) {
        console.error("Failed to trigger incident", err);
        setIncidentStatus('ERROR');
        setIsTriggered(false);
      }
    }
  };

  const connectSSE = () => {
    closeSSE(); // guard against duplicate connections
    const source = new EventSource(`${API_BASE}/api/events`);
    sseRef.current = source;
    source.addEventListener('state_update', (e) => {
      const event = JSON.parse(e.data);
      handleEvent(event);
    });
    source.onerror = () => console.warn('SSE connection lost, retrying...');
  };

  const injectFailure = async (failureType) => {
    await fetch(`${API_BASE}/api/inject-failure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ failure_type: failureType })
    });
  };

  const approveFix = async () => {
    setIsApproving(true);
    try {
      await fetch(`${API_BASE}/api/approve-fix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
    } catch (err) {
      console.error("Failed to approve fix", err);
    } finally {
      setIsApproving(false);
    }
  };

  const simulateWebhook = async () => {
    setIsTriggered(true);
    setIncidentStatus('STARTING...');
    setAwaitingApproval(false);
    
    if (MOCK_MODE) {
      triggerIncident();
      return;
    }
    
    try {
      await fetch(`${API_BASE}/api/webhooks/alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alert_type: 'HIGH_LATENCY',
          alert_name: 'API Gateway High Latency',
          service: 'api-gateway',
          component: 'api-gateway',
          severity: severity,
          source: 'pagerduty',
          timestamp: new Date().toISOString()
        })
      });
      connectSSE();
    } catch (err) {
      console.error("Failed to simulate webhook", err);
      setIncidentStatus('ERROR');
    }
  };

  const getEventColorClass = (type) => {
    const map = {
      'INCIDENT_CREATED': 'color-info',
      'PLAN_CREATED': 'color-info',
      'AGENT_STARTED': 'color-info',
      'AGENT_THINKING': 'color-info',
      'AGENT_COMPLETED': 'color-success',
      'AGENT_FAILED': 'color-error',
      'REPLAN_TRIGGERED': 'color-warning',
      'PLAN_UPDATED': 'color-warning',
      'RESOLVED': 'color-success',
      'ESCALATED': 'color-error',
      'AWAITING_APPROVAL': 'color-warning',
      'APPROVED': 'color-info',
      'SPAWNED_AGENTS': 'color-info'
    };
    // Graceful fallback for unknown event types - OC2
    return map[type] || 'color-info';
  };
  
  const getStatusIcon = (status) => {
    if (status.includes('NORMAL') || status === 'RESOLVED') return 'check_circle';
    if (status === 'ESCALATED' || status.includes('ERROR')) return 'error';
    if (status === 'AWAITING_APPROVAL') return 'warning';
    if (status === 'STARTING...') return 'pending';
    if (status === 'PLANNING' || status === 'INVESTIGATING' || status === 'DIAGNOSING' || status === 'REMEDIATING') return 'sync';
    return 'info';
  };

  const formatTime = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const renderArrow = (start, end, label) => {
    const dx = 40;
    const path = `M ${start.x} ${start.y} C ${start.x + dx} ${start.y}, ${end.x - dx} ${end.y}, ${end.x} ${end.y}`;
    return (
      <g key={`${start.x}-${end.y}`}>
        <path d={path} fill="none" stroke="#444" strokeWidth="1.5" strokeDasharray="4 4" markerEnd="url(#arrowhead)" />
        {label && (
          <text x={(start.x + end.x)/2} y={(start.y + end.y)/2 - 8} fill="#888" fontSize="11" fontFamily="monospace" fontStyle="italic" textAnchor="middle">
            {label}
          </text>
        )}
      </g>
    );
  };

  const getAgentStatus = (id) => steps.find(s => s.agent === id)?.status || 'IDLE';
  const getAgentThinking = (id) => steps.find(s => s.agent === id)?.thinking || '';

  const nodes = [
    { id: 'Planner', name: '1. Planner', role: 'Initializes Plan', x: 100, y: 230 },
    { id: 'LogAnalyzer', name: '2. Log Analyzer', role: 'Scans Logs', x: 320, y: 110 },
    { id: 'MetricsAgent', name: '3. Metrics Agent', role: 'Analyzes Metrics', x: 320, y: 350 },
    { id: 'Diagnostician', name: '4. Diagnostician', role: 'Correlates Data', x: 540, y: 230 },
    { id: 'Remediator', name: '5. Remediator', role: 'Executes Fix', x: 760, y: 230 },
  ];

  return (
    <>
      <div style={{ width: '100vw', height: '100vh', position: 'fixed', top: 0, left: 0, zIndex: 0, pointerEvents: 'none', display: 'flex', justifyContent: 'center', background: '#050505', overflow: 'hidden' }}>
        <div style={{ width: '1080px', height: '1080px', position: 'relative', top: '-15%', opacity: 0.7 }}>
          <LightRays
            raysOrigin="top-center"
            raysColor="#ffffff"
            raysSpeed={1.5}
            lightSpread={0.4}
            rayLength={3.8}
            pulsating={false}
            fadeDistance={1.4}
            saturation={1}
            followMouse
            mouseInfluence={0.1}
            noiseAmount={0}
            distortion={0}
          />
        </div>
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '60vh', background: 'linear-gradient(to bottom, transparent, #050505)' }}></div>
      </div>

      <div style={{ zoom: 0.8, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <header className="hero">
          <h1 className="title">AEGIS</h1>
        <p className="subtitle">Autonomous Emergency Grid for Incident Self-healing</p>
      </header>

      <div className="dashboard">
        <div className="dashboard-left">
          <h2 className="panel-title">Execution lifecycle with state-aware self-healing</h2>
          
          <div className="incident-header">
            <div className="status-badge">
              <span className="material-symbols-rounded" style={{
                color: incidentStatus.includes('NORMAL') || incidentStatus === 'RESOLVED' ? 'var(--google-green)' : 
                       incidentStatus === 'ESCALATED' ? 'var(--google-red)' :
                       incidentStatus === 'AWAITING_APPROVAL' ? 'var(--google-yellow)' : 'var(--google-blue)'
              }}>
                {getStatusIcon(incidentStatus)}
              </span>
              {incidentStatus}
            </div>
          </div>

          {/* AWAITING_APPROVAL Banner - OC1 */}
          {awaitingApproval && (
            <div className="approval-banner">
              <span className="material-symbols-rounded">warning</span>
              <span>Remediation requires human approval — confidence below threshold or action not in allow-list</span>
              <button 
                className="btn-approve" 
                onClick={approveFix}
                disabled={isApproving}
              >
                {isApproving ? (
                  <span className="material-symbols-rounded" style={{ animation: 'spin 2s linear infinite' }}>hourglass_empty</span>
                ) : (
                  <span className="material-symbols-rounded">check_circle</span>
                )}
                {isApproving ? 'Approving...' : 'Approve Fix'}
              </button>
            </div>
          )}

          <div className="flowchart-container">
            <div className="flowchart-inner">
              {/* <div className="flowchart-header">
                <h2 className="flowchart-title">Autonomous Agent Recovery Flow</h2>
                <p className="flowchart-subtitle">Execution lifecycle with state-aware self-healing</p>
              </div> */}
              
              <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0, zIndex: 1 }}>
                <defs>
                  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#444" />
                  </marker>
                </defs>
                {renderArrow({x: 190, y: 230}, {x: 230, y: 110}, 'Delegates')}
                {renderArrow({x: 190, y: 230}, {x: 230, y: 350}, 'Delegates')}
                {renderArrow({x: 410, y: 110}, {x: 450, y: 230}, 'Output')}
                {renderArrow({x: 410, y: 350}, {x: 450, y: 230}, 'Output')}
                {renderArrow({x: 630, y: 230}, {x: 670, y: 230}, 'Routes to')}
              </svg>

              {nodes.map(node => {
                const status = getAgentStatus(node.id);
                const thinking = getAgentThinking(node.id);
                return (
                  <div key={node.id} className="flow-node-wrapper" style={{ left: node.x, top: node.y }}>
                    <div className={`flow-node status-${status.toLowerCase()}`}>
                      <p className="node-title">{node.name}</p>
                      <p className="node-role">{node.role}</p>
                    </div>
                    {thinking && (
                      <div className="flow-node-thinking">{thinking}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="cta-container">
            <button 
              className="btn-primary" 
              onClick={triggerIncident}
              disabled={isTriggered}
            >
              {isTriggered ? (
                <span className="material-symbols-rounded" style={{ animation: 'spin 2s linear infinite' }}>hourglass_empty</span>
              ) : (
                <span className="material-symbols-rounded">play_arrow</span>
              )}
              {isTriggered ? 'Triggered...' : 'Trigger Incident'}
            </button>
          </div>

          {/* Severity Selector - OC3 */}
          <div className="severity-selector">
            <span className="severity-label">Severity:</span>
            <div className="severity-buttons">
              {['P1', 'P2', 'P3'].map(s => (
                <button
                  key={s}
                  className={`severity-btn ${severity === s ? 'active' : ''}`}
                  onClick={() => setSeverity(s)}
                  disabled={isTriggered}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Webhook Demo Button - OC4 */}
          <div className="webhook-demo">
            <button 
              className="btn-secondary webhook-btn" 
              onClick={simulateWebhook}
              disabled={isTriggered}
            >
              <span className="material-symbols-rounded">webhook</span>
              Simulate PagerDuty Alert
            </button>
          </div>

          {isTriggered && (
            <div className="failure-buttons">
              <button className="btn-secondary" onClick={() => injectFailure('LOG_SOURCE_UNAVAILABLE')}>
                Inject: Log Failure
              </button>
              <button className="btn-secondary" onClick={() => injectFailure('REMEDIATION_FAILED')}>
                Inject: Remediation Failure
              </button>
            </div>
          )}
        </div>

        <div className="dashboard-right">
          <h2 className="panel-title">System Logs</h2>
          <div className="timeline-container" ref={timelineRef}>
            <div className="timeline">
              {history.map((event) => (
                <div key={event.id} className="timeline-entry">
                  <span className="timeline-time">{formatTime(event.timestamp)}</span>
                  <div className="timeline-content">
                    <span className={`timeline-badge ${getEventColorClass(event.event_type)}`}>
                      {event.event_type.replace(/_/g, ' ')}
                    </span>
                    <span className="timeline-detail">{event.message}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* <div className="credibility-strip">
        Powered by <strong>Antigravity Agent</strong>
      </div> */}
      </div>

      {/* Toast notifications for APPROVED / SPAWNED_AGENTS */}
      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
      
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );
}

export default App;
