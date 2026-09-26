import React, { useState, useEffect, useRef } from 'react';
import { Play, Activity, CheckCircle, AlertTriangle, PlayCircle, Loader2 } from 'lucide-react';

const MOCK_MODE = false;
const API_BASE = ''; // Proxy handles this

const INITIAL_AGENTS = [
    { id: 'Planner', name: 'Planner', role: 'Decomposes alert into subtasks', icon: '🧠' },
    { id: 'LogAnalyzer', name: 'Log Analyzer', role: 'Scans application logs', icon: '📋' },
    { id: 'MetricsAgent', name: 'Metrics Agent', role: 'Analyzes infrastructure metrics', icon: '📊' },
    { id: 'Diagnostician', name: 'Diagnostician', role: 'Correlates findings', icon: '🔬' },
    { id: 'Remediator', name: 'Remediator', role: 'Executes fixes', icon: '🔧' }
];

function App() {
  const [incidentStatus, setIncidentStatus] = useState('ALL SYSTEMS NORMAL');
  const [steps, setSteps] = useState([]);
  const [history, setHistory] = useState([]);
  const [isTriggered, setIsTriggered] = useState(false);
  const timelineRef = useRef(null);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [history]);

  const handleEvent = (event) => {
    const data = event.data;
    if (data.status) setIncidentStatus(data.status);
    if (data.steps) setSteps(data.steps);
    
    setHistory(prev => [...prev, {
      id: Date.now() + Math.random(),
      timestamp: event.timestamp || new Date().toISOString(),
      event_type: event.event_type,
      message: data.message || ''
    }]);
  };

  const triggerIncident = async () => {
    setIsTriggered(true);
    setIncidentStatus('STARTING...');
    
    if (MOCK_MODE) {
      await replayMockEvents();
    } else {
      try {
        await fetch(`${API_BASE}/api/trigger-incident`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            alert_type: 'HIGH_LATENCY',
            service: 'api-gateway',
            severity: 'P1'
          })
        });
        connectSSE();
      } catch (err) {
        console.error("Failed to trigger incident", err);
        setIncidentStatus('ERROR: CONNECTION FAILED');
      }
    }
  };

  const connectSSE = () => {
    const source = new EventSource(`${API_BASE}/api/events`);
    source.addEventListener('state_update', (e) => {
      const event = JSON.parse(e.data);
      handleEvent(event);
    });
    source.onerror = () => console.warn('SSE connection lost, retrying...');
  };

  const replayMockEvents = async () => {
    try {
      const response = await fetch('/mock_events.json');
      const events = await response.json();
      for (const event of events) {
        await new Promise(resolve => setTimeout(resolve, event.delay || 1000));
        handleEvent(event);
      }
    } catch (err) {
      console.error("Failed to load mock events", err);
    }
  };

  const injectFailure = async (failureType) => {
    if (MOCK_MODE) {
      alert(`Failure ${failureType} injected (mock mode doesn't affect replay natively)`);
      return;
    }
    await fetch(`${API_BASE}/api/inject-failure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ failure_type: failureType })
    });
  };

  const getEventTypeClass = (type) => {
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
  };

  const formatTime = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <>
      <div className="floating-avatar avatar-1">
        <span className="icon">🧠</span>
        <div className="info">
          <span className="name">Planner</span>
          <span className="status">Ready</span>
        </div>
      </div>
      <div className="floating-avatar avatar-2">
        <span className="icon">🔬</span>
        <div className="info">
          <span className="name">Diagnostician</span>
          <span className="status">Ready</span>
        </div>
      </div>
      <div className="floating-avatar avatar-3">
        <span className="icon">🔧</span>
        <div className="info">
          <span className="name">Remediator</span>
          <span className="status">Ready</span>
        </div>
      </div>

      <header className="hero">
        <h1 className="title"><em>AEGIS</em></h1>
        <p className="subtitle">Autonomous Emergency Grid for Incident Self-healing</p>
      </header>

      <main className="glass-card" id="main-panel">
        <div className="incident-header">
          <span className={`status-badge status-${incidentStatus.toLowerCase().replace(/ /g, '-')}`}>
            {incidentStatus}
          </span>
        </div>

        <div className="agent-panel">
          {INITIAL_AGENTS.map(agent => {
            const step = steps.find(s => s.agent === agent.id);
            const status = step?.status || 'IDLE';
            return (
              <div key={agent.id} className="agent-row">
                <span className="agent-icon">{agent.icon}</span>
                <div className="agent-info">
                  <span className="agent-name">{agent.name}</span>
                  <span className="agent-role">{agent.role}</span>
                </div>
                <span className={`status-chip status-${status.toLowerCase()}`}>
                  {status}
                </span>
              </div>
            );
          })}
        </div>

        <div className="cta-container">
          <button 
            className="btn-primary" 
            onClick={triggerIncident}
            disabled={isTriggered}
          >
            {isTriggered ? <><Loader2 size={18} className="animate-spin" /> Triggered...</> : <><PlayCircle size={18} /> Trigger Incident</>}
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
      </main>

      <div className="timeline-container">
        <h3 className="timeline-title">Incident Timeline</h3>
        <div className="timeline" ref={timelineRef}>
          {history.length === 0 && (
            <div className="timeline-entry badge-info" style={{ opacity: 0.5, justifyContent: 'center' }}>
              <span className="timeline-detail" style={{textAlign: 'center'}}>Waiting for events...</span>
            </div>
          )}
          {history.map((event) => (
            <div key={event.id} className={`timeline-entry ${getEventTypeClass(event.event_type)}`}>
              <span className="timeline-time">{formatTime(event.timestamp)}</span>
              <span className={`timeline-badge ${getEventTypeClass(event.event_type)}`}>{event.event_type}</span>
              <span className="timeline-detail">{event.message}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="credibility-strip">
        Powered by <strong>Antigravity Agent</strong> · Interactions API · FastAPI · SSE
      </div>
    </>
  );
}

export default App;
