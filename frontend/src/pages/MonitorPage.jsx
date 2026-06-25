import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Monitor, Play, Square, AlertTriangle, Clock,
  ChevronDown, ChevronUp, Trash2, Shield, Eye, StopCircle, Bell, X
} from 'lucide-react';
import {
  startSession, stopSession, getSessions, getSessionDetail,
  getAllAlerts, analyzeFrame, deleteSession
} from '../api';
import PrivacyToastContainer from '../components/PrivacyToast';

const riskColor = r => ({ CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e', SAFE:'#22c55e' }[r] || '#6b7280');
const riskBg    = r => ({ CRITICAL:'rgba(220,38,38,0.1)', HIGH:'rgba(239,68,68,0.1)', MEDIUM:'rgba(245,158,11,0.1)', LOW:'rgba(34,197,94,0.1)', SAFE:'rgba(34,197,94,0.1)' }[r] || 'transparent');
const TYPE_ICON = { aadhaar:'🪪', pan:'🪪', credit_card:'💳', email:'📧', phone:'📱', password:'🔑', otp:'🔒', face_detected:'👤', dob:'📅' };
const INTERVALS = [{ label:'3 sec', value:3000 },{ label:'5 sec', value:5000 },{ label:'10 sec', value:10000 },{ label:'30 sec', value:30000 }];

/* ─── per-session state shape ──────────────────────────────────────────────
   activeSessions[id] = {
     stream, captureVideo, captureCanvas, intervalId,
     scanCount, alertCount, lastResult, liveAlerts, label
   }
────────────────────────────────────────────────────────────────────────── */

export default function MonitorPage() {
  const [activeSessions, setActiveSessions] = useState({});
  const [sessions,   setSessions]   = useState([]);
  const [alerts,     setAlerts]     = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [detail,     setDetail]     = useState(null);
  const [intervalMs, setIntervalMs] = useState(5000);
  const [error,      setError]      = useState('');
  const [starting,   setStarting]   = useState(false);
  const [toasts,     setToasts]     = useState([]);
  const [notifPerm,  setNotifPerm]  = useState(
    typeof Notification !== 'undefined' ? Notification.permission : 'denied'
  );
  const [sourcesList, setSourcesList] = useState([]);
  const [showSourcesModal, setShowSourcesModal] = useState(false);
  const [sourceTab, setSourceTab] = useState('screen');


  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback((risk, score, types, sessionId, scanId) => {
    if (!['MEDIUM','HIGH','CRITICAL'].includes(risk)) return;
    const id = Date.now();
    setToasts(prev => [{ id, risk, score, types, sessionId, scanId }, ...prev].slice(0, 4));
    // Browser OS notification when tab not visible
    if (typeof Notification !== 'undefined' && Notification.permission === 'granted' && document.hidden) {
      const icons = { CRITICAL:'🔴', HIGH:'🟠', MEDIUM:'🟡' };
      try {
        new Notification(`${icons[risk]||'⚠️'} PrivacyShield — ${risk} Risk on Screen!`, {
          body: `Score: ${score}/100\nFound: ${(types||[]).slice(0,3).join(', ')}`,
          tag: 'privacy-screen-alert',
        });
      } catch {}
    }
  }, []);

  const requestNotifPermission = useCallback(async () => {
    if (typeof Notification === 'undefined') return;
    const perm = await Notification.requestPermission();
    setNotifPerm(perm);
  }, []);

  const loadHistory = useCallback(async () => {
    try { const [s, a] = await Promise.all([getSessions(), getAllAlerts()]); setSessions(s); setAlerts(a); } catch {}
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // cleanup on unmount
  useEffect(() => () => {
    Object.values(activeSessions).forEach(s => {
      clearInterval(s.intervalId);
      s.stream?.getTracks().forEach(t => t.stop());
    });
  }, []); // eslint-disable-line

  // ── update one session's live state ────────────────────────────────────────
  const updateSession = useCallback((sid, patch) => {
    setActiveSessions(prev => {
      if (!prev[sid]) return prev;
      return { ...prev, [sid]: { ...prev[sid], ...patch } };
    });
  }, []);

  // ── capture one frame for a session ────────────────────────────────────────
  const captureAndAnalyze = useCallback(async (sid) => {
    setActiveSessions(prev => {
      const s = prev[sid];
      if (!s) return prev;
      const { captureVideo, captureCanvas } = s;
      const w = captureVideo.videoWidth  || 1280;
      const h = captureVideo.videoHeight || 720;
      if (w === 0) return prev;
      captureCanvas.width  = w;
      captureCanvas.height = h;
      captureCanvas.getContext('2d').drawImage(captureVideo, 0, 0, w, h);
      captureCanvas.toBlob(async blob => {
        if (!blob || blob.size < 500) return;
        const fd = new FormData();
        fd.append('session_id', sid);
        fd.append('ocr_text',   '');
        fd.append('save_image', 'true');
        fd.append('screenshot', blob, 'frame.png');
        try {
          const res = await analyzeFrame(fd);
          // Fire toast notification for MEDIUM+ risks
          if (res.should_alert) {
            addToast(res.risk_level, res.score, res.finding_types, sid, res.scan_id);
          }
          setActiveSessions(p => {
            if (!p[sid]) return p;
            const cur = p[sid];
            return {
              ...p,
              [sid]: {
                ...cur,
                scanCount:  res.scan_number,
                lastResult: res,
                alertCount: res.should_alert ? cur.alertCount + 1 : cur.alertCount,
                liveAlerts: res.should_alert ? [res, ...cur.liveAlerts].slice(0, 6) : cur.liveAlerts,
              },
            };
          });
        } catch {}
      }, 'image/png');
      return prev;
    });
  }, [addToast]);

  // ── start new session — picks source via Electron IPC only ─────────────────
  const handleStart = async () => {
    if (starting) return;
    setError('');

    if (window.electronAPI && typeof window.electronAPI.getSources === 'function') {
      // ── Electron: show our custom in-app source picker ────────────────────
      setStarting(true);
      try {
        const sources = await window.electronAPI.getSources();
        setSourcesList(sources);
        setSourceTab('screen');
        setShowSourcesModal(true);
      } catch (err) {
        setError('Failed to fetch capture sources: ' + err.message);
      } finally {
        setStarting(false);
      }
      return;
    }

    // ── Browser (dev/localhost): we do NOT use getDisplayMedia because it
    //    triggers the OS browser screen-share picker which looks wrong.
    //    Instead, show a helpful message directing the user to run the EXE.
    setError(
      '⚠️ Screen Monitor requires the PrivacyShield desktop app. ' +
      'Open the installed EXE to use this feature with full screen capture support.'
    );
  };

  const handleSelectSource = async (source) => {
    setShowSourcesModal(false);
    setStarting(true);
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          mandatory: {
            chromeMediaSource: 'desktop',
            chromeMediaSourceId: source.id,
            minWidth: 1280,
            maxWidth: 1920,
            minHeight: 720,
            maxHeight: 1080
          }
        }
      });
    } catch (err) {
      setError('Failed to capture selected source: ' + err.message);
      setStarting(false);
      return;
    }
    await initStreamSession(stream, source.name);
  };

  const initStreamSession = async (stream, customLabel = null) => {
    // Offscreen video for capturing frames (NOT in DOM → no layout impact)
    const captureVideo = document.createElement('video');
    captureVideo.srcObject = stream;
    captureVideo.muted = true;
    captureVideo.playsInline = true;
    await captureVideo.play().catch(() => {});

    // Offscreen canvas
    const captureCanvas = document.createElement('canvas');

    // Create backend session
    let sess;
    try { sess = await startSession(); }
    catch (e) {
      setError(e.response?.data?.detail || 'Failed to create session on server.');
      stream.getTracks().forEach(t => t.stop());
      setStarting(false);
      return;
    }

    const sid = sess.session_id;

    // Detect what the user is sharing (tab title from stream track)
    const track = stream.getVideoTracks()[0];
    const label = customLabel || track?.label || `Session #${sid}`;

    const iid = setInterval(() => captureAndAnalyze(sid), intervalMs);

    setActiveSessions(prev => ({
      ...prev,
      [sid]: { stream, captureVideo, captureCanvas, intervalId: iid, label, scanCount: 0, alertCount: 0, lastResult: null, liveAlerts: [] },
    }));

    // If user stops sharing
    track.onended = () => handleStopSession(sid);

    setStarting(false);
    loadHistory();
  };

  // ── stop one session ──────────────────────────────────────────────────────
  const handleStopSession = useCallback(async (sid) => {
    setActiveSessions(prev => {
      const s = prev[sid];
      if (s) { clearInterval(s.intervalId); s.stream?.getTracks().forEach(t => t.stop()); }
      const next = { ...prev }; delete next[sid]; return next;
    });
    try { await stopSession(sid); } catch {}
    loadHistory();
  }, [loadHistory]);

  // ── stop all sessions ─────────────────────────────────────────────────────
  const handleStopAll = useCallback(async () => {
    const ids = Object.keys(activeSessions).map(Number);
    setActiveSessions(prev => {
      Object.values(prev).forEach(s => { clearInterval(s.intervalId); s.stream?.getTracks().forEach(t => t.stop()); });
      return {};
    });
    for (const id of ids) { try { await stopSession(id); } catch {} }
    loadHistory();
  }, [activeSessions, loadHistory]);

  const handleDelete = async (id) => { try { await deleteSession(id); loadHistory(); } catch {} };

  const loadDetail = async (id) => {
    if (expandedId === id) { setExpandedId(null); setDetail(null); return; }
    setExpandedId(id);
    try { setDetail(await getSessionDetail(id)); } catch {}
  };

  const pulseStyle = { animation: 'pulse 1.5s ease-in-out infinite' };
  const anyActive  = Object.keys(activeSessions).length > 0;

  return (
    <>
    <div>
      <style>{`
        @keyframes pulse   { 0%,100%{opacity:1} 50%{opacity:0.4} }
        @keyframes slideIn { from{transform:translateY(-6px);opacity:0} to{transform:translateY(0);opacity:1} }
        @keyframes toastIn { from{transform:translateX(340px);opacity:0} to{transform:translateX(0);opacity:1} }
      `}</style>

      {/* ── Header controls ── */}
      <div className="card" style={{ padding:'20px 24px', marginBottom:20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
          <div className="section-title" style={{ margin:0 }}>
            <Monitor size={16} color="var(--accent)"/> Screenshot Monitor
          </div>
          {anyActive && (
            <span style={{ fontSize:12, fontWeight:700, color:'#ef4444', display:'flex', alignItems:'center', gap:6 }}>
              <span style={{ width:8, height:8, borderRadius:'50%', background:'#ef4444', display:'inline-block', ...pulseStyle }}/>
              {Object.keys(activeSessions).length} session(s) LIVE
            </span>
          )}
        </div>
        <p style={{ color:'var(--text-secondary)', fontSize:13, marginBottom:16 }}>
          Select a window or screen to monitor for PII in real-time.
          Click <strong>Start New Session</strong> to choose what to share.
          Requires the <strong>PrivacyShield desktop app</strong>.
          You can run multiple sessions at once.
        </p>

        {notifPerm !== 'granted' && (
          <div style={{ marginBottom: 12, padding: '10px 14px', borderRadius: 8,
            background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)',
            display: 'flex', alignItems: 'center', gap: 10 }}>
            <Bell size={15} color="#f59e0b" />
            <span style={{ fontSize: 12, color: '#f59e0b', flex: 1 }}>
              Enable browser notifications to get alerts even when this tab is in the background.
            </span>
            <button className="btn btn-sm btn-primary" onClick={requestNotifPermission}
              style={{ fontSize: 11, padding: '4px 10px', background: '#f59e0b', border: 'none' }}>
              Enable Alerts
            </button>
          </div>
        )}

        {error && <div className="alert alert-error" style={{ marginBottom:14 }}><AlertTriangle size={14}/> {error}</div>}

        <div style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'center' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <span style={{ fontSize:12, color:'var(--text-secondary)' }}>Interval:</span>
            {INTERVALS.map(o => (
              <button key={o.value} onClick={() => setIntervalMs(o.value)}
                className={`btn btn-sm ${intervalMs===o.value?'btn-primary':'btn-secondary'}`}>
                {o.label}
              </button>
            ))}
          </div>
          <button className="btn btn-primary" style={{ minWidth:170 }}
            onClick={handleStart} disabled={starting}>
            <Play size={14}/> {starting ? 'Waiting for share…' : 'Start New Session'}
          </button>
          {anyActive && (
            <button className="btn btn-danger" style={{ minWidth:120 }} onClick={handleStopAll}>
              <Square size={14}/> Stop All
            </button>
          )}
        </div>
        <p style={{ fontSize:11, color:'var(--text-muted)', marginTop:10 }}>
          ✅ Works on Chrome, Edge, Firefox. Safari requires macOS 13+.
        </p>
      </div>

      {/* ── Active session cards (each compact with inline preview) ── */}
      {Object.entries(activeSessions).map(([sid, state]) => (
        <div key={sid} className="card" style={{ padding:0, overflow:'hidden', marginBottom:16, border:'2px solid rgba(34,197,94,0.35)' }}>

          {/* Card header */}
          <div style={{ padding:'10px 16px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:10, background:'rgba(34,197,94,0.04)' }}>
            <span style={{ width:9, height:9, borderRadius:'50%', background:'#22c55e', display:'inline-block', ...pulseStyle }}/>
            <div style={{ flex:1, minWidth:0 }}>
              <span style={{ fontWeight:700, fontSize:13 }}>Session #{sid} </span>
              <span style={{ fontSize:11, color:'var(--text-muted)', wordBreak:'break-all' }}>
                — {state.label.length > 60 ? state.label.slice(0, 60) + '…' : state.label}
              </span>
            </div>
            <button className="btn btn-danger btn-sm"
              onClick={() => handleStopSession(Number(sid))}>
              <StopCircle size={13}/> Stop
            </button>
          </div>

          <div style={{ display:'flex', gap:0 }}>
            {/* Left: compact inline preview */}
            <div style={{ width:260, flexShrink:0, background:'#000', borderRight:'1px solid var(--border)', position:'relative' }}>
              <video
                autoPlay muted playsInline
                ref={el => { if (el && el.srcObject !== state.stream) { el.srcObject = state.stream; el.play().catch(() => {}); } }}
                style={{ width:'100%', height:150, objectFit:'contain', display:'block' }}
              />
              <div style={{ position:'absolute', top:6, left:8, fontSize:10, fontWeight:700, color:'#22c55e', background:'rgba(0,0,0,0.6)', padding:'2px 6px', borderRadius:4 }}>
                LIVE
              </div>
            </div>

            {/* Right: stats + live alerts */}
            <div style={{ flex:1, minWidth:0 }}>
              {/* Stats row */}
              <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', borderBottom:'1px solid var(--border)' }}>
                {[
                  { label:'Frames',     value: state.scanCount,   color:'var(--accent)' },
                  { label:'Alerts',     value: state.alertCount,  color: state.alertCount > 0 ? '#ef4444' : 'var(--text-muted)' },
                  { label:'Last Score', value: state.lastResult ? `${state.lastResult.score}/100` : '--',
                    color: state.lastResult ? riskColor(state.lastResult.risk_level) : 'var(--text-muted)' },
                  { label:'Status',     value: state.lastResult?.risk_level || 'SCANNING',
                    color: state.lastResult ? riskColor(state.lastResult.risk_level) : 'var(--accent)' },
                ].map((s, i) => (
                  <div key={i} style={{ padding:'10px 12px', borderRight: i < 3 ? '1px solid var(--border)' : 'none', textAlign:'center' }}>
                    <div style={{ fontSize:10, color:'var(--text-muted)', textTransform:'uppercase', fontWeight:600, marginBottom:3 }}>{s.label}</div>
                    <div style={{ fontSize:16, fontWeight:800, color: s.color }}>{s.value}</div>
                  </div>
                ))}
              </div>
              {/* Live alerts for this session */}
              <div style={{ maxHeight:92, overflowY:'auto' }}>
                {state.liveAlerts.length === 0 ? (
                  <div style={{ padding:'16px 16px', fontSize:12, color:'var(--text-muted)' }}>No PII detected yet…</div>
                ) : state.liveAlerts.map((a, i) => (
                  <div key={i} style={{ padding:'6px 14px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:8, animation:'slideIn 0.25s ease' }}>
                    <span style={{ fontSize:14, fontWeight:800, color:riskColor(a.risk_level), minWidth:32 }}>{a.score}</span>
                    <span style={{ padding:'1px 7px', borderRadius:10, fontSize:10, fontWeight:700, background:riskBg(a.risk_level), color:riskColor(a.risk_level) }}>{a.risk_level}</span>
                    <div style={{ display:'flex', gap:4, flexWrap:'wrap', flex:1 }}>
                      {(a.finding_types||[]).map(t => (
                        <span key={t} style={{ fontSize:10, background:'var(--accent-light)', color:'var(--accent)', borderRadius:5, padding:'1px 6px' }}>
                          {TYPE_ICON[t]||'⚠️'} {t}
                        </span>
                      ))}
                    </div>
                    <span style={{ fontSize:10, color:'var(--text-muted)' }}>#{a.scan_number}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ))}

      {/* ── Session History ── */}
      <div className="card" style={{ padding:0, overflow:'hidden' }}>
        <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:8 }}>
          <Clock size={15} style={{ color:'var(--accent)' }}/>
          <span className="section-title" style={{ margin:0 }}>Session History ({sessions.length})</span>
        </div>
        {sessions.length === 0 ? (
          <div style={{ padding:48, textAlign:'center', color:'var(--text-secondary)' }}>
            <Monitor size={36} style={{ opacity:0.2, display:'block', margin:'0 auto 12px' }}/>
            <p style={{ fontWeight:600 }}>No sessions yet</p>
            <p style={{ fontSize:13 }}>Click "Start New Session" to begin.</p>
          </div>
        ) : sessions.map(s => {
          const liveState = activeSessions[s.session_id];
          const isLive    = !!liveState;
          return (
            <div key={s.session_id}>
              <div style={{ padding:'12px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:12, cursor:'pointer' }}
                onClick={() => loadDetail(s.session_id)}>
                <div style={{ width:9, height:9, borderRadius:'50%', flexShrink:0, background: isLive ? '#22c55e' : 'var(--text-muted)', ...(isLive ? pulseStyle : {}) }}/>
                <div style={{ flex:1 }}>
                  <span style={{ fontWeight:600, fontSize:13 }}>Session #{s.session_id} </span>
                  <span style={{ fontSize:11, padding:'2px 7px', borderRadius:10, marginLeft:6,
                    background: isLive ? 'rgba(34,197,94,0.12)' : 'var(--bg-base)',
                    color: isLive ? '#22c55e' : 'var(--text-muted)',
                    border:`1px solid ${isLive ? 'rgba(34,197,94,0.3)' : 'var(--border)'}` }}>
                    {isLive ? 'LIVE' : s.status.toUpperCase()}
                  </span>
                  <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:2 }}>{new Date(s.started_at).toLocaleString()}</div>
                </div>
                <div style={{ textAlign:'center', minWidth:50 }}>
                  <div style={{ fontSize:16, fontWeight:800, color:'var(--accent)' }}>{isLive ? liveState.scanCount : s.scan_count}</div>
                  <div style={{ fontSize:10, color:'var(--text-muted)' }}>frames</div>
                </div>
                <div style={{ textAlign:'center', minWidth:50 }}>
                  <div style={{ fontSize:16, fontWeight:800, color: s.alert_count > 0 ? '#ef4444' : 'var(--text-muted)' }}>{isLive ? liveState.alertCount : s.alert_count}</div>
                  <div style={{ fontSize:10, color:'var(--text-muted)' }}>alerts</div>
                </div>
                {isLive && (
                  <button className="btn btn-danger btn-sm" onClick={e => { e.stopPropagation(); handleStopSession(s.session_id); }}>
                    <StopCircle size={12}/> Stop
                  </button>
                )}
                <button className="btn btn-danger btn-sm" onClick={e => { e.stopPropagation(); handleDelete(s.session_id); }}>
                  <Trash2 size={12}/>
                </button>
                {expandedId === s.session_id ? <ChevronUp size={15}/> : <ChevronDown size={15}/>}
              </div>

              {expandedId === s.session_id && detail && (
                <div style={{ padding:'16px 20px', background:'var(--bg-base)', borderBottom:'1px solid var(--border)' }}>
                  {detail.alerts.length === 0 ? (
                    <div style={{ textAlign:'center', padding:'16px 0', color:'var(--success)', fontWeight:600 }}>✅ No PII detected in this session</div>
                  ) : (
                    <div className="table-container">
                      <table>
                        <thead><tr><th>Time</th><th>Score</th><th>Risk</th><th>Detected Types</th><th>Action</th></tr></thead>
                        <tbody>
                          {detail.alerts.map(a => (
                            <tr key={a.alert_id}>
                              <td style={{ fontSize:11 }}>{new Date(a.timestamp).toLocaleTimeString()}</td>
                              <td style={{ fontWeight:700, color:riskColor(a.risk_level) }}>{a.score}</td>
                              <td><span style={{ padding:'2px 8px', borderRadius:10, fontSize:11, fontWeight:700, background:riskBg(a.risk_level), color:riskColor(a.risk_level) }}>{a.risk_level}</span></td>
                              <td><div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>{a.finding_types.map(t => <span key={t} style={{ fontSize:10, background:'var(--accent-light)', color:'var(--accent)', borderRadius:5, padding:'2px 6px' }}>{TYPE_ICON[t]||'⚠️'} {t}</span>)}</div></td>
                              <td>{a.scan_id && <button className="btn btn-secondary btn-sm" style={{ fontSize:11 }} onClick={() => window.location.href=`/recommendations?id=${a.scan_id}`}>Tips</button>}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── All Alerts ── */}
      {alerts.length > 0 && (
        <div className="card" style={{ padding:0, overflow:'hidden', marginTop:20 }}>
          <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:8 }}>
            <Shield size={15} style={{ color:'var(--accent)' }}/>
            <span className="section-title" style={{ margin:0 }}>All Alerts ({alerts.length})</span>
          </div>
          <div className="table-container">
            <table>
              <thead><tr><th>Session</th><th>Time</th><th>Score</th><th>Risk</th><th>Types</th><th>Action</th></tr></thead>
              <tbody>
                {alerts.slice(0,20).map(a => (
                  <tr key={a.alert_id}>
                    <td style={{ fontWeight:600 }}>#{a.session_id}</td>
                    <td style={{ fontSize:11, color:'var(--text-muted)' }}>{new Date(a.timestamp).toLocaleString()}</td>
                    <td style={{ fontWeight:700, color:riskColor(a.risk_level) }}>{a.score}</td>
                    <td><span style={{ padding:'2px 8px', borderRadius:10, fontSize:11, fontWeight:700, background:riskBg(a.risk_level), color:riskColor(a.risk_level) }}>{a.risk_level}</span></td>
                    <td style={{ fontSize:11 }}>{(a.finding_types||[]).join(', ')}</td>
                    <td>{a.scan_id && <button className="btn btn-secondary btn-sm" style={{ fontSize:11 }} onClick={() => window.location.href=`/recommendations?id=${a.scan_id}`}>View Tips</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>

      {/* ── Electron Window/Screen Picker Modal ── */}
      {showSourcesModal && (() => {
        const screens  = sourcesList.filter(s => s.type === 'screen');
        const browsers = sourcesList.filter(s => s.type === 'browser');
        const windows  = sourcesList.filter(s => s.type === 'window');

        return (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(8px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 9999, padding: 24,
            animation: 'fadeIn 0.2s ease-out'
          }}>
            <div className="card" style={{
              maxWidth: 860, width: '100%', maxHeight: '88vh',
              display: 'flex', flexDirection: 'column', padding: 0,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.6)',
              overflow: 'hidden', borderRadius: 18,
            }}>
              {/* Modal Header */}
              <div style={{ padding: '20px 24px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <div>
                    <h3 style={{ fontSize: 17, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                      Choose what to share
                    </h3>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
                      The app will be able to see the contents of your screen
                    </p>
                  </div>
                  <button className="btn btn-secondary btn-sm" onClick={() => setShowSourcesModal(false)}>
                    <X size={15} />
                  </button>
                </div>

                {/* 3 Tabs */}
                <div style={{ display: 'flex', gap: 0, marginBottom: -1 }}>
                  {[
                    { key: 'screen',  label: 'Entire Screen',  icon: '🖥️', count: screens.length  },
                    { key: 'browser', label: 'Browser Tab',    icon: '🌐', count: browsers.length },
                    { key: 'window',  label: 'Window',         icon: '⬜', count: windows.length  },
                  ].map(tab => {
                    const isActive = (sourceTab || 'screen') === tab.key;
                    return (
                      <button
                        key={tab.key}
                        onClick={() => setSourceTab(tab.key)}
                        style={{
                          padding: '10px 20px', border: 'none', cursor: 'pointer',
                          fontSize: 13, fontWeight: isActive ? 700 : 500,
                          background: 'transparent',
                          color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                          borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                          transition: 'all 0.2s',
                          display: 'flex', alignItems: 'center', gap: 6,
                        }}
                      >
                        <span style={{ fontSize: 15 }}>{tab.icon}</span>
                        {tab.label}
                        <span style={{
                          fontSize: 10, fontWeight: 700,
                          background: isActive ? 'var(--accent)' : 'var(--border)',
                          color: isActive ? '#fff' : 'var(--text-muted)',
                          borderRadius: 10, padding: '1px 6px',
                        }}>{tab.count}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Source Grid */}
              <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
                {(() => {
                  const activeTab = sourceTab || 'screen';
                  const list = activeTab === 'screen' ? screens : activeTab === 'browser' ? browsers : windows;

                  if (list.length === 0) {
                    return (
                      <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-secondary)' }}>
                        <div style={{ fontSize: 36, marginBottom: 12 }}>
                          {activeTab === 'browser' ? '🌐' : activeTab === 'screen' ? '🖥️' : '⬜'}
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>
                          {activeTab === 'browser'
                            ? 'No browser windows found. Open Chrome, Edge, or Firefox first.'
                            : activeTab === 'screen'
                            ? 'No screens detected.'
                            : 'No application windows found.'}
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                      gap: 14,
                    }}>
                      {list.map(source => (
                        <div
                          key={source.id}
                          onClick={() => handleSelectSource(source)}
                          style={{
                            borderRadius: 12, border: '1.5px solid var(--border)',
                            background: 'var(--bg-base)', cursor: 'pointer',
                            display: 'flex', flexDirection: 'column', gap: 0,
                            transition: 'transform 0.15s, border-color 0.15s, box-shadow 0.15s',
                            overflow: 'hidden',
                          }}
                          className="source-card"
                          title={source.name}
                        >
                          <style>{`
                            .source-card:hover {
                              border-color: var(--accent) !important;
                              transform: translateY(-3px);
                              box-shadow: 0 8px 24px rgba(59,130,246,0.15);
                            }
                          `}</style>
                          {/* Thumbnail */}
                          <div style={{
                            width: '100%', height: 108,
                            background: '#09090b',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            overflow: 'hidden', position: 'relative',
                          }}>
                            {source.thumbnail ? (
                              <img
                                src={source.thumbnail}
                                alt={source.name}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              />
                            ) : (
                              <div style={{ fontSize: 28 }}>
                                {source.type === 'screen' ? '🖥️' : source.type === 'browser' ? '🌐' : '⬜'}
                              </div>
                            )}
                            {/* Type badge */}
                            <div style={{
                              position: 'absolute', top: 6, right: 6,
                              fontSize: 9, fontWeight: 700,
                              background: source.type === 'screen' ? 'rgba(34,197,94,0.9)' : source.type === 'browser' ? 'rgba(59,130,246,0.9)' : 'rgba(100,116,139,0.9)',
                              color: '#fff', padding: '2px 6px', borderRadius: 4,
                            }}>
                              {source.type.toUpperCase()}
                            </div>
                          </div>
                          {/* Label */}
                          <div style={{ padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 6 }}>
                            {source.appIcon && (
                              <img src={source.appIcon} alt="" style={{ width: 16, height: 16, flexShrink: 0 }} />
                            )}
                            <span style={{
                              fontSize: 11, fontWeight: 600, color: 'var(--text-primary)',
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            }}>
                              {source.name.length > 30 ? source.name.slice(0, 28) + '…' : source.name}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>

              {/* Footer */}
              <div style={{
                padding: '14px 24px', borderTop: '1px solid var(--border)',
                display: 'flex', justifyContent: 'flex-end', gap: 10,
                background: 'var(--bg-base)',
              }}>
                <button className="btn btn-secondary" onClick={() => setShowSourcesModal(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Antivirus-style Toast Notifications ── */}
      <PrivacyToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
