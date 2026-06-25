import React, { useState, useEffect, useRef } from 'react';
import api from '../api';
import {
  Shield, ShieldOff, ShieldCheck, AlertTriangle, CheckCircle,
  Clock, FolderOpen, Activity, Trash2, RefreshCw, Plus, X, FolderPlus
} from 'lucide-react';

const RISK_COLOR = {
  SAFE:     '#4ade80',
  LOW:      '#a3e635',
  MEDIUM:   '#facc15',
  HIGH:     '#fb923c',
  CRITICAL: '#f87171',
};
const RISK_BG = {
  SAFE:     'rgba(74,222,128,0.08)',
  LOW:      'rgba(163,230,53,0.08)',
  MEDIUM:   'rgba(250,204,21,0.1)',
  HIGH:     'rgba(251,146,60,0.1)',
  CRITICAL: 'rgba(248,113,113,0.12)',
};

const FOLDER_ICONS = {
  Downloads: '⬇️', Desktop: '🖥️', Documents: '📄',
  Pictures: '🖼️', Videos: '🎬', Music: '🎵',
  OneDrive: '☁️',
};

function RiskBadge({ level }) {
  const color = RISK_COLOR[level] || '#94a3b8';
  const bg    = RISK_BG[level]    || 'rgba(148,163,184,0.08)';
  return (
    <span style={{
      padding: '2px 10px', borderRadius: 20, fontSize: 11,
      fontWeight: 700, letterSpacing: '0.05em',
      color, background: bg, border: `1px solid ${color}40`,
    }}>{level}</span>
  );
}

function TimeSince({ iso }) {
  if (!iso) return null;
  const diff = Math.floor((Date.now() - new Date(iso + 'Z').getTime()) / 1000);
  if (diff < 60)   return <span>{diff}s ago</span>;
  if (diff < 3600) return <span>{Math.floor(diff / 60)}m ago</span>;
  return <span>{Math.floor(diff / 3600)}h ago</span>;
}

export default function BackgroundAgentPage() {
  const [status,       setStatus]       = useState(null);
  const [folders,      setFolders]      = useState([]);   // system folder list
  const [loading,      setLoading]      = useState(true);
  const [toggling,     setToggling]     = useState(false);
  const [folderLoading,setFolderLoading]= useState(false);
  const [customPath,   setCustomPath]   = useState('');
  const [customError,  setCustomError]  = useState('');
  const [customSuccess,setCustomSuccess]= useState('');
  const [error,        setError]        = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const pollRef = useRef(null);

  // Fetch agent status
  const fetchStatus = async () => {
    try {
      const res = await api.get('/agent/status');
      setStatus(res.data);
      setError('');
    } catch { setError('Cannot reach backend.'); }
    finally { setLoading(false); }
  };

  // Fetch all candidate system folders
  const fetchFolders = async () => {
    try {
      const res = await api.get('/agent/folders');
      setFolders(res.data.system_folders || []);
    } catch {}
  };

  useEffect(() => {
    fetchStatus();
    fetchFolders();
    pollRef.current = setInterval(() => { fetchStatus(); fetchFolders(); }, 3000);
    return () => clearInterval(pollRef.current);
  }, []);

  // Start/Stop toggle
  const handleToggle = async () => {
    setToggling(true); setError(''); setSuccessMessage('');
    try {
      if (status?.running) {
        await api.post('/agent/stop');
        setSuccessMessage('Background Protection stopped successfully.');
      } else {
        await api.post('/agent/start', { folders: [] });
        setSuccessMessage('Background Protection started successfully.');
      }
      await fetchStatus();
      await fetchFolders();
      // Auto-clear success message after 4.5 seconds
      setTimeout(() => setSuccessMessage(''), 4500);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Action failed.');
    } finally { setToggling(false); }
  };

  // Toggle a system folder on/off
  const toggleFolder = async (folder) => {
    setFolderLoading(true);
    try {
      if (folder.watched) {
        await api.post('/agent/folders/remove', { path: folder.path });
      } else {
        await api.post('/agent/folders/add', { path: folder.path });
      }
      await fetchFolders();
      await fetchStatus();
    } catch (e) {
      setError(e?.response?.data?.message || 'Could not update folder.');
    } finally { setFolderLoading(false); }
  };

  // Add custom folder path
  const handleAddCustom = async () => {
    if (!customPath.trim()) return;
    setCustomError(''); setCustomSuccess('');
    try {
      const res = await api.post('/agent/folders/add', { path: customPath.trim() });
      if (res.data.ok) {
        setCustomSuccess(`✅ Now watching: ${customPath.trim()}`);
        setCustomPath('');
        await fetchFolders();
        await fetchStatus();
      } else {
        setCustomError(res.data.message || 'Could not add folder.');
      }
    } catch (e) {
      setCustomError(e?.response?.data?.detail || 'Invalid path or folder does not exist.');
    }
  };

  const handleClearEvents = async () => {
    await api.delete('/agent/events');
    fetchStatus();
  };

  const isRunning = status?.running;

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '8px 0' }}>

      {/* ── Hero toggle ─────────────────────────────────────────────── */}
      <div style={{
        background: isRunning
          ? 'linear-gradient(135deg, rgba(34,197,94,0.12), rgba(22,163,74,0.05))'
          : 'linear-gradient(135deg, rgba(100,116,139,0.07), rgba(71,85,105,0.03))',
        border: `1.5px solid ${isRunning ? 'rgba(34,197,94,0.3)' : 'var(--border)'}`,
        borderRadius: 20, padding: '32px 28px', marginBottom: 20,
        display: 'flex', alignItems: 'center', gap: 28,
        transition: 'all 0.4s ease',
      }}>
        {/* Shield icon */}
        <div style={{
          width: 88, height: 88, flexShrink: 0, borderRadius: '50%',
          background: isRunning
            ? 'radial-gradient(circle, rgba(34,197,94,0.22), rgba(22,163,74,0.06))'
            : 'radial-gradient(circle, rgba(100,116,139,0.15), rgba(71,85,105,0.05))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: isRunning ? '0 0 36px rgba(34,197,94,0.22)' : 'none',
          animation: isRunning ? 'pulse-ring 2.2s ease-in-out infinite' : 'none',
          transition: 'all 0.4s ease',
        }}>
          {isRunning
            ? <ShieldCheck size={44} color="#22c55e" strokeWidth={1.5} />
            : <ShieldOff   size={44} color="#64748b" strokeWidth={1.5} />}
        </div>

        {/* Text + button */}
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 21, fontWeight: 800, marginBottom: 4, color: 'var(--text-primary)' }}>
            Background Protection
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>
            {isRunning
              ? `✅ Actively monitoring ${status?.watched_folders?.length || 0} folder(s). Any sensitive file detected will trigger an instant desktop alert.`
              : `🔴 Protection is OFF. Enable it to automatically scan new files and get notified when PII is detected.`}
          </p>
          <button
            onClick={handleToggle}
            disabled={toggling || loading}
            style={{
              padding: '11px 32px', borderRadius: 50, border: 'none',
              cursor: toggling ? 'wait' : 'pointer',
              fontWeight: 800, fontSize: 14, letterSpacing: '0.03em',
              transition: 'all 0.3s ease',
              background: isRunning
                ? 'linear-gradient(135deg, #dc2626, #991b1b)'
                : 'linear-gradient(135deg, #22c55e, #16a34a)',
              color: '#fff',
              boxShadow: isRunning
                ? '0 4px 18px rgba(220,38,38,0.3)'
                : '0 4px 18px rgba(34,197,94,0.3)',
              opacity: (toggling || loading) ? 0.65 : 1,
            }}
          >
            {toggling ? '...' : isRunning ? '⏹ Stop Protection' : '▶ Start Protection'}
          </button>
        </div>

        {/* Stats */}
        {isRunning && (
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 10,
            padding: '14px 18px',
            background: 'rgba(34,197,94,0.06)',
            border: '1px solid rgba(34,197,94,0.2)',
            borderRadius: 14, minWidth: 110, flexShrink: 0,
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#22c55e' }}>{status?.total_scanned ?? 0}</div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Scanned</div>
            </div>
            <div style={{ height: 1, background: 'rgba(34,197,94,0.2)' }} />
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#f87171' }}>{status?.total_alerts ?? 0}</div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Alerts</div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div style={{
          background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.3)',
          borderRadius: 10, padding: '10px 16px', marginBottom: 16,
          color: '#f87171', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {successMessage && (
        <div style={{
          background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)',
          borderRadius: 10, padding: '10px 16px', marginBottom: 16,
          color: '#22c55e', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <CheckCircle size={14} color="#22c55e" /> {successMessage}
        </div>
      )}

      {/* ── Folder Manager ───────────────────────────────────────────── */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 16, overflow: 'hidden', marginBottom: 20,
      }}>
        {/* Header */}
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'rgba(96,165,250,0.04)',
        }}>
          <FolderOpen size={15} color="#60a5fa" />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            Watched Folders
          </span>
          <span style={{
            marginLeft: 'auto', fontSize: 11, color: 'var(--text-secondary)',
          }}>
            Toggle to add/remove from monitoring
          </span>
        </div>

        {/* System folders grid */}
        <div style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            System Folders
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: 8,
          }}>
            {folders.map((folder, i) => {
              const label = folder.label || folder.path.split(/[\\/]/).pop();
              const icon  = FOLDER_ICONS[label] || '📁';
              return (
                <button
                  key={i}
                  onClick={() => folder.exists && toggleFolder(folder)}
                  disabled={folderLoading || !folder.exists}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 14px', borderRadius: 10,
                    border: `1.5px solid ${folder.watched ? 'rgba(34,197,94,0.4)' : 'var(--border)'}`,
                    background: folder.watched
                      ? 'rgba(34,197,94,0.08)'
                      : folder.exists ? 'var(--bg)' : 'rgba(100,116,139,0.04)',
                    cursor: folder.exists ? 'pointer' : 'not-allowed',
                    opacity: folder.exists ? 1 : 0.4,
                    transition: 'all 0.2s ease',
                    textAlign: 'left',
                  }}
                >
                  <span style={{ fontSize: 18, flexShrink: 0 }}>{icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 12, fontWeight: 600,
                      color: folder.watched ? '#22c55e' : 'var(--text-primary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>{label}</div>
                    <div style={{
                      fontSize: 10, color: 'var(--text-secondary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {folder.exists ? folder.path.replace(/\\/g, '/').split('/').slice(-2).join('/') : 'Not found on this PC'}
                    </div>
                  </div>
                  {/* Toggle indicator */}
                  <div style={{
                    width: 28, height: 16, borderRadius: 8, flexShrink: 0,
                    background: folder.watched ? '#22c55e' : 'rgba(100,116,139,0.3)',
                    position: 'relative', transition: 'background 0.2s',
                  }}>
                    <div style={{
                      position: 'absolute', top: 2, left: folder.watched ? 14 : 2,
                      width: 12, height: 12, borderRadius: '50%', background: '#fff',
                      transition: 'left 0.2s',
                    }} />
                  </div>
                </button>
              );
            })}
          </div>

          {/* Custom folder input */}
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Add Custom Folder Path
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                value={customPath}
                onChange={e => { setCustomPath(e.target.value); setCustomError(''); setCustomSuccess(''); }}
                onKeyDown={e => e.key === 'Enter' && handleAddCustom()}
                placeholder="e.g. C:\Users\sujay\MyFolder  or  D:\Work"
                style={{
                  flex: 1, padding: '9px 14px', borderRadius: 10,
                  border: `1.5px solid ${customError ? 'rgba(248,113,113,0.5)' : 'var(--border)'}`,
                  background: 'var(--bg)', color: 'var(--text-primary)', fontSize: 12,
                  fontFamily: 'monospace', outline: 'none',
                }}
              />
              <button
                onClick={handleAddCustom}
                disabled={!customPath.trim()}
                style={{
                  padding: '9px 16px', borderRadius: 10, border: 'none',
                  background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                  color: '#fff', fontWeight: 700, fontSize: 12,
                  cursor: customPath.trim() ? 'pointer' : 'not-allowed',
                  opacity: customPath.trim() ? 1 : 0.5,
                  display: 'flex', alignItems: 'center', gap: 5,
                  transition: 'opacity 0.2s',
                }}
              >
                <Plus size={13} /> Add
              </button>
            </div>
            {customError   && <div style={{ fontSize: 11, color: '#f87171', marginTop: 6 }}>⚠️ {customError}</div>}
            {customSuccess && <div style={{ fontSize: 11, color: '#4ade80', marginTop: 6 }}>{customSuccess}</div>}
            <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
              Tip: You can add any folder from your PC. The agent will watch it for new files.
            </div>
          </div>
        </div>
      </div>

      {/* ── Live Activity Feed ───────────────────────────────────────── */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 16, overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Activity size={15} color="#60a5fa" />
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Live Activity Feed</span>
            {isRunning && (
              <span style={{
                width: 7, height: 7, borderRadius: '50%', background: '#22c55e',
                display: 'inline-block', boxShadow: '0 0 6px #22c55e',
                animation: 'blink 1.2s ease-in-out infinite',
              }} />
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => { fetchStatus(); fetchFolders(); }}
              style={{
                background: 'transparent', border: '1px solid var(--border)',
                borderRadius: 8, padding: '4px 10px', cursor: 'pointer',
                color: 'var(--text-secondary)', fontSize: 11,
                display: 'flex', alignItems: 'center', gap: 4,
              }}
            >
              <RefreshCw size={11} /> Refresh
            </button>
            {status?.recent_events?.length > 0 && (
              <button
                onClick={handleClearEvents}
                style={{
                  background: 'transparent', border: '1px solid rgba(248,113,113,0.3)',
                  borderRadius: 8, padding: '4px 10px', cursor: 'pointer',
                  color: '#f87171', fontSize: 11,
                  display: 'flex', alignItems: 'center', gap: 4,
                }}
              >
                <Trash2 size={11} /> Clear
              </button>
            )}
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)', fontSize: 13 }}>Loading...</div>
        ) : !status?.recent_events?.length ? (
          <div style={{ padding: 48, textAlign: 'center' }}>
            <Clock size={34} color="var(--text-secondary)" strokeWidth={1.2} style={{ marginBottom: 12 }} />
            <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
              {isRunning
                ? 'Monitoring active — events will appear here as files are detected.'
                : 'Start protection to begin monitoring your folders.'}
            </div>
          </div>
        ) : (
          <div>
            {status.recent_events.map((ev, i) => (
              <div key={ev.id ?? i} style={{
                padding: '12px 20px', borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 14,
                background: ev.alerted ? RISK_BG[ev.risk_level] : 'transparent',
              }}>
                <div style={{ flexShrink: 0 }}>
                  {ev.alerted
                    ? <AlertTriangle size={16} color={RISK_COLOR[ev.risk_level] || '#fb923c'} />
                    : <CheckCircle   size={16} color="#4ade80" />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{ev.filename}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                    {ev.findings_count} finding{ev.findings_count !== 1 ? 's' : ''}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 800, color: RISK_COLOR[ev.risk_level] || 'var(--text-primary)' }}>
                    {ev.score}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>/ 100</div>
                </div>
                <div style={{ flexShrink: 0 }}><RiskBadge level={ev.risk_level} /></div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', flexShrink: 0, minWidth: 50, textAlign: 'right' }}>
                  <TimeSince iso={ev.timestamp} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse-ring {
          0%,100% { box-shadow: 0 0 36px rgba(34,197,94,0.22); }
          50%      { box-shadow: 0 0 56px rgba(34,197,94,0.42); }
        }
        @keyframes blink {
          0%,100% { opacity: 1; }
          50%      { opacity: 0.15; }
        }
      `}</style>
    </div>
  );
}
