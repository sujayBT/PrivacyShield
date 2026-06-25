import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getScans, getRecommendations } from '../api';
import { Lightbulb, AlertTriangle, Shield, CheckCircle, X, ZoomIn } from 'lucide-react';
import Lightbox from '../components/Lightbox';

const STORAGE_KEY = 'recommendationsPageState';

const iconMap = {
  'alert-triangle': AlertTriangle,
  'shield':         Shield,
  'check-circle':   CheckCircle,
  'mail':           Lightbulb,
  'phone':          Lightbulb,
  'key':            Lightbulb,
};

const sevConfig = {
  HIGH:   { color: '#ef4444', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.25)',   leftBar: '#ef4444', icon: AlertTriangle },
  MEDIUM: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.25)',  leftBar: '#f59e0b', icon: Shield },
  LOW:    { color: '#22c55e', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.25)',   leftBar: '#22c55e', icon: CheckCircle },
};

// Zoom modal for a single recommendation card
const RecModal = ({ rec, onClose }) => {
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  if (!rec) return null;
  const cfg = sevConfig[rec.severity] || sevConfig.LOW;
  const Icon = iconMap[rec.icon] || Lightbulb;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)',
        zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'fadeUp 0.2s ease', cursor: 'zoom-out', padding: 24
      }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--bg-card)', borderRadius: 16,
          border: `2px solid ${cfg.border}`,
          maxWidth: 560, width: '100%',
          boxShadow: `0 0 60px ${cfg.color}33`,
          overflow: 'hidden', cursor: 'default', animation: 'fadeUp 0.2s ease'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid var(--border)',
          display: 'flex', gap: 14, alignItems: 'flex-start',
          borderLeft: `4px solid ${cfg.leftBar}`
        }}>
          <div style={{
            width: 42, height: 42, borderRadius: 10, flexShrink: 0,
            background: cfg.bg, display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Icon size={20} color={cfg.color} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', marginBottom: 4 }}>{rec.title}</div>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: cfg.color, fontWeight: 700 }}>{rec.severity}</span>
              <span style={{ color: 'var(--text-muted)' }}> · {rec.category}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%',
              width: 32, height: 32, cursor: 'pointer', color: 'var(--text-primary)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0
            }}
          >✕</button>
        </div>
        {/* Advice */}
        <div style={{ padding: '20px 24px' }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
            Recommended Actions
          </div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {rec.advice.map((tip, i) => (
              <li key={i} style={{
                display: 'flex', gap: 10, alignItems: 'flex-start',
                padding: '10px 14px', borderRadius: 8,
                background: cfg.bg, border: `1px solid ${cfg.border}`,
                fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6
              }}>
                <span style={{ color: cfg.color, fontWeight: 800, flexShrink: 0, marginTop: 1 }}>→</span>
                {tip}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default function RecommendationsPage() {
  const [scans, setScans] = useState([]);
  const [searchParams] = useSearchParams();
  const defaultId = searchParams.get('id');
  const [recs, setRecs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [zoomedRec, setZoomedRec] = useState(null);

  // Persist selected scan
  const [selected, setSelected] = useState(() => {
    if (defaultId) return defaultId;
    try { return localStorage.getItem(STORAGE_KEY) || ''; } catch { return ''; }
  });

  const persistSelected = useCallback((id) => {
    setSelected(id);
    try { if (id) localStorage.setItem(STORAGE_KEY, id); else localStorage.removeItem(STORAGE_KEY); } catch {}
  }, []);

  const fetchRecs = useCallback(async (id) => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getRecommendations(id);
      setRecs(data.recommendations);
    } catch (e) {
      console.error('Failed to get recommendations', e);
      setRecs([]);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { getScans().then(setScans); }, []);

  // Auto-load recs if we have a saved/url selection
  useEffect(() => {
    if (defaultId) { persistSelected(defaultId); fetchRecs(defaultId); }
    else if (selected) { fetchRecs(selected); }
  }, []);

  const handleSelect = (e) => {
    const id = e.target.value;
    persistSelected(id);
    setRecs(null);
    if (id) fetchRecs(id);
  };

  const handleClear = () => {
    persistSelected('');
    setRecs(null);
  };

  const scan = selected ? scans.find(s => s.id === Number(selected)) : null;

  return (
    <div>
      {/* Zoom Modal */}
      {zoomedRec && <RecModal rec={zoomedRec} onClose={() => setZoomedRec(null)} />}

      {/* Control Panel */}
      <div className="card" style={{ padding: '20px 24px', marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
          <div className="section-title" style={{ margin: 0 }}>
            <Lightbulb size={16} color="var(--accent)" /> Security Recommendations
          </div>
          {(scan || recs) && (
            <button className="btn btn-danger btn-sm" onClick={handleClear} title="Clear selection">
              <X size={13} /> Clear
            </button>
          )}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
          Get personalized security tips based on the sensitive data detected in your scan.
          {scan && <span style={{ color: 'var(--accent)', fontWeight: 600 }}> Selection saved.</span>}
        </p>
        <select className="input" style={{ maxWidth: 400 }} value={selected} onChange={handleSelect}>
          <option value="">— Select a scan —</option>
          {scans.map(s => (
            <option key={s.id} value={s.id}>
              #{s.id} — {s.filename} ({s.risk_level})
            </option>
          ))}
        </select>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <div className="spinner" style={{ width: 32, height: 32, margin: '0 auto 16px', borderWidth: 3, borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Generating recommendations...</p>
        </div>
      )}

      {/* Recommendations Grid */}
      {recs && !loading && recs.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 16 }}>
          {recs.map((rec, i) => {
            const cfg = sevConfig[rec.severity] || sevConfig.LOW;
            const Icon = iconMap[rec.icon] || Lightbulb;
            return (
              <div
                key={i}
                className="animate-up"
                style={{
                  background: 'var(--bg-card)',
                  border: `1px solid ${cfg.border}`,
                  borderLeft: `4px solid ${cfg.leftBar}`,
                  borderRadius: 12,
                  overflow: 'hidden',
                  animationDelay: `${i * 0.07}s`,
                  display: 'flex', flexDirection: 'column',
                  boxShadow: 'var(--shadow-sm)',
                  transition: 'box-shadow 0.2s, transform 0.2s',
                }}
                onMouseEnter={e => e.currentTarget.style.boxShadow = `0 4px 20px ${cfg.color}22`}
                onMouseLeave={e => e.currentTarget.style.boxShadow = 'var(--shadow-sm)'}
              >
                {/* Card Header */}
                <div style={{ padding: '16px 18px', borderBottom: `1px solid ${cfg.border}`, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: 9, flexShrink: 0,
                    background: cfg.bg, display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <Icon size={18} color={cfg.color} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 2, lineHeight: 1.3 }}>
                      {rec.title}
                    </div>
                    <div style={{ fontSize: 11 }}>
                      <span style={{ color: cfg.color, fontWeight: 700 }}>{rec.severity}</span>
                      <span style={{ color: 'var(--text-muted)' }}> · {rec.category}</span>
                    </div>
                  </div>
                  {/* Zoom button */}
                  <button
                    onClick={() => setZoomedRec(rec)}
                    title="Expand"
                    style={{
                      background: 'var(--bg-base)', border: '1px solid var(--border)',
                      borderRadius: 6, cursor: 'pointer', padding: '4px 6px',
                      color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
                      flexShrink: 0, transition: 'color 0.15s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = cfg.color}
                    onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
                  >
                    <ZoomIn size={14} />
                  </button>
                </div>

                {/* Advice list — capped height with scroll */}
                <div style={{ padding: '12px 18px 16px', flex: 1 }}>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {rec.advice.slice(0, 4).map((tip, j) => (
                      <li key={j} style={{
                        display: 'flex', gap: 8, alignItems: 'flex-start',
                        fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55
                      }}>
                        <span style={{ color: cfg.color, fontWeight: 800, flexShrink: 0, marginTop: 1 }}>→</span>
                        <span>{tip}</span>
                      </li>
                    ))}
                    {rec.advice.length > 4 && (
                      <li style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                        +{rec.advice.length - 4} more — <button
                          onClick={() => setZoomedRec(rec)}
                          style={{ background: 'none', border: 'none', color: cfg.color, cursor: 'pointer', fontWeight: 600, fontSize: 11, padding: 0 }}
                        >expand to see all</button>
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {recs && !loading && recs.length === 0 && (
        <div className="card" style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>No critical recommendations</div>
          <div style={{ fontSize: 13 }}>Great — minimal risk detected in this file.</div>
        </div>
      )}

      {/* No selection */}
      {!recs && !loading && (
        <div className="card" style={{ padding: 64, textAlign: 'center', color: 'var(--text-secondary)' }}>
          <div style={{ fontSize: 52, marginBottom: 16 }}>💡</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
            Select a scan to see recommendations
          </div>
          <div style={{ fontSize: 13 }}>Personalised security tips based on what was found in your file.</div>
        </div>
      )}
    </div>
  );
}
