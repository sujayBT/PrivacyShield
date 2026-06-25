import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getScans, getRemediationPlan } from '../api';
import {
  ShieldCheck, AlertTriangle, Zap, Clock, CheckCircle,
  ChevronDown, ChevronUp, ExternalLink, Wrench, X
} from 'lucide-react';

// ── Constants ──────────────────────────────────────────────────────────────────
const URGENCY_CONFIG = {
  IMMEDIATE:    { color: '#f87171', bg: 'rgba(248,113,113,0.10)', icon: Zap,        label: 'IMMEDIATE'    },
  WITHIN_24H:   { color: '#fb923c', bg: 'rgba(251,146,60,0.10)',  icon: AlertTriangle, label: 'WITHIN 24H' },
  WITHIN_WEEK:  { color: '#facc15', bg: 'rgba(250,204,21,0.10)',  icon: Clock,      label: 'WITHIN WEEK'  },
};

const RISK_COLOR = {
  SAFE: '#4ade80', LOW: '#a3e635', MEDIUM: '#facc15',
  HIGH: '#fb923c', CRITICAL: '#f87171',
};

const FINDING_LABELS = {
  aadhaar: '🪪 Aadhaar', pan_card: '💳 PAN Card', credit_card: '💳 Credit Card',
  cvv: '🔒 CVV', password: '🔑 Password', email: '📧 Email', phone: '📱 Phone',
  otp: '🔢 OTP', dob: '📅 Date of Birth', face_detected: '👤 Face', id_card_visible: '🪪 ID Card',
};

// ── Sub-components ─────────────────────────────────────────────────────────────
function UrgencyBadge({ urgency }) {
  const cfg = URGENCY_CONFIG[urgency] || URGENCY_CONFIG.WITHIN_WEEK;
  const Icon = cfg.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 12px', borderRadius: 20, fontSize: 11, fontWeight: 700,
      color: cfg.color, background: cfg.bg,
      border: `1px solid ${cfg.color}40`,
    }}>
      <Icon size={11} /> {cfg.label}
    </span>
  );
}

function RemediationCard({ plan, index, onNavigate }) {
  const [expanded, setExpanded] = useState(index === 0);
  const [checked, setChecked]   = useState({});
  const label = FINDING_LABELS[plan.finding_type] || `📋 ${plan.finding_type}`;
  const done  = Object.values(checked).filter(Boolean).length;

  return (
    <div style={{
      background: 'var(--card)', border: `1.5px solid ${expanded ? 'rgba(96,165,250,0.25)' : 'var(--border)'}`,
      borderRadius: 16, overflow: 'hidden', marginBottom: 12,
      transition: 'border-color 0.2s',
    }}>
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%', padding: '16px 20px', display: 'flex',
          alignItems: 'center', gap: 12, background: 'transparent',
          border: 'none', cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div style={{ fontSize: 18, flexShrink: 0 }}>{label.split(' ')[0]}</div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 3 }}>
            {label.slice(label.indexOf(' ') + 1)} &nbsp;
            <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)' }}>
              ({plan.count} instance{plan.count !== 1 ? 's' : ''} found)
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <UrgencyBadge urgency={plan.urgency} />
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{plan.urgency_label}</span>
          </div>
        </div>

        {/* Progress */}
        <div style={{ textAlign: 'right', flexShrink: 0, marginRight: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: done === plan.steps.length ? '#4ade80' : 'var(--text-secondary)' }}>
            {done}/{plan.steps.length}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>steps done</div>
        </div>

        {expanded ? <ChevronUp size={16} color="var(--text-secondary)" /> : <ChevronDown size={16} color="var(--text-secondary)" />}
      </button>

      {/* Progress bar */}
      <div style={{ height: 3, background: 'var(--border)', margin: '0 20px' }}>
        <div style={{
          height: '100%', background: done === plan.steps.length ? '#4ade80' : '#60a5fa',
          width: `${plan.steps.length ? (done / plan.steps.length) * 100 : 0}%`,
          borderRadius: 2, transition: 'width 0.3s ease',
        }} />
      </div>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: '16px 20px' }}>

          {/* Steps checklist */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
              Action Steps
            </div>
            {plan.steps.map((step, i) => (
              <div
                key={i}
                onClick={() => setChecked(c => ({ ...c, [i]: !c[i] }))}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: '8px 12px', borderRadius: 8, marginBottom: 4,
                  cursor: 'pointer', transition: 'background 0.15s',
                  background: checked[i] ? 'rgba(74,222,128,0.06)' : 'transparent',
                }}
              >
                {/* Checkbox */}
                <div style={{
                  width: 18, height: 18, borderRadius: 5, flexShrink: 0,
                  border: `2px solid ${checked[i] ? '#4ade80' : 'var(--border)'}`,
                  background: checked[i] ? '#4ade80' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginTop: 1, transition: 'all 0.15s',
                }}>
                  {checked[i] && <CheckCircle size={12} color="#000" strokeWidth={3} />}
                </div>
                <span style={{
                  fontSize: 13, lineHeight: 1.5,
                  color: checked[i] ? 'var(--text-secondary)' : 'var(--text-primary)',
                  textDecoration: checked[i] ? 'line-through' : 'none',
                  transition: 'all 0.15s',
                }}>
                  <strong style={{ color: checked[i] ? 'var(--text-secondary)' : '#60a5fa' }}>Step {i + 1}:</strong> {step}
                </span>
              </div>
            ))}
          </div>

          {/* Tools — full width now that Legal References is removed */}
          {plan.tools?.length > 0 && (
            <div style={{
              background: 'rgba(96,165,250,0.05)', border: '1px solid rgba(96,165,250,0.2)',
              borderRadius: 10, padding: '12px 14px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                <Wrench size={13} color="#60a5fa" />
                <span style={{ fontSize: 11, fontWeight: 700, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Helpful Tools</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {plan.tools.map((tool, i) => {
                  const isInternal = tool.url.startsWith('/');
                  return (
                    <a
                      key={i}
                      href={isInternal ? undefined : tool.url}
                      target={isInternal ? undefined : '_blank'}
                      rel={isInternal ? undefined : 'noreferrer'}
                      onClick={isInternal ? (e) => { e.preventDefault(); onNavigate(tool.url); } : undefined}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 5,
                        padding: '5px 12px', borderRadius: 20,
                        background: 'rgba(96,165,250,0.10)', border: '1px solid rgba(96,165,250,0.3)',
                        fontSize: 12, color: '#60a5fa', textDecoration: 'none',
                        fontWeight: 600, cursor: 'pointer', transition: 'background 0.15s',
                      }}
                    >
                      <ExternalLink size={11} /> {tool.name}
                    </a>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function RemediationPage() {
  const navigate = useNavigate();
  const [scans,   setScans]   = useState([]);
  const [scanId,  setScanId]  = useState('');
  const [plan,    setPlan]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  // Load scan list on mount — do NOT auto-select anything
  useEffect(() => {
    getScans().then(data => {
      const sorted = [...data].sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date));
      setScans(sorted);
    }).catch(() => {});
  }, []);

  const load = useCallback(async (id) => {
    if (!id) return;
    setLoading(true); setError(''); setPlan(null);
    try {
      const data = await getRemediationPlan(id);
      setPlan(data);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not load remediation plan.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-load immediately when user picks a scan — no Load button needed
  const handleSelect = (e) => {
    const id = e.target.value;
    setScanId(id);
    setPlan(null);
    setError('');
    if (id) load(id);
  };

  const handleClear = () => {
    setScanId('');
    setPlan(null);
    setError('');
  };

  // Removed: auto-load on scanId change — user must click Load explicitly

  const immediateCount = plan?.plans?.filter(p => p.urgency === 'IMMEDIATE').length ?? 0;

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '8px 0' }}>

      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(251,191,36,0.10), rgba(245,158,11,0.04))',
        border: '1.5px solid rgba(251,191,36,0.25)',
        borderRadius: 18, padding: '24px 28px', marginBottom: 24,
        display: 'flex', alignItems: 'center', gap: 20,
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16,
          background: 'linear-gradient(135deg, #f59e0b, #d97706)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, boxShadow: '0 4px 24px rgba(245,158,11,0.3)'
        }}>
          <Wrench size={32} color="#ffffff" />
        </div>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 4, color: 'var(--text-primary)' }}>
            Remediation Plan
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
            Clear, step-by-step action plan with real tools to fix every privacy risk found.
          </p>
        </div>
        {plan && (
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Scan Risk Level</div>
            <div style={{
              fontSize: 16, fontWeight: 800,
              color: RISK_COLOR[plan.risk_level] || 'var(--text-primary)',
            }}>{plan.risk_level}</div>
          </div>
        )}
      </div>

      {/* Scan selector — styled like Recommendations page */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 14, padding: '18px 22px', marginBottom: 20,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
            <ShieldCheck size={16} color="#f59e0b" /> Remediation Plan
          </div>
          {(scanId || plan) && (
            <button
              onClick={handleClear}
              style={{
                padding: '5px 12px', borderRadius: 8,
                border: '1px solid rgba(248,113,113,0.35)',
                background: 'rgba(248,113,113,0.07)',
                color: '#f87171', fontSize: 12, fontWeight: 700,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
              }}
            >
              <X size={12} /> Clear
            </button>
          )}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '0 0 14px' }}>
          Select a scan and get a clear, step-by-step action plan to fix every privacy risk found.
        </p>
        <select
          value={scanId}
          onChange={handleSelect}
          style={{
            maxWidth: 440, width: '100%', padding: '9px 13px', borderRadius: 9,
            border: '1.5px solid var(--border)', background: 'var(--bg)',
            color: 'var(--text-primary)', fontSize: 13, outline: 'none',
          }}
        >
          <option value="">— Select a scan —</option>
          {scans.map(s => (
            <option key={s.id} value={s.id}>
              #{s.id} — {s.filename} ({s.risk_level}, Score: {s.score})
            </option>
          ))}
        </select>
      </div>


      {/* Error */}
      {error && (
        <div style={{
          background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.3)',
          borderRadius: 10, padding: '10px 16px', marginBottom: 16,
          color: '#f87171', fontSize: 13,
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Loading spinner */}
      {loading && (
        <div style={{ padding: 64, textAlign: 'center', color: 'var(--text-secondary)' }}>
          <div className="spinner" style={{ width: 32, height: 32, margin: '0 auto 16px', borderWidth: 3 }} />
          <div style={{ fontSize: 13 }}>Generating remediation plan...</div>
        </div>
      )}

      {/* Empty state — shown when nothing is selected */}
      {!plan && !loading && !error && (
        <div style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 14, padding: 64, textAlign: 'center', color: 'var(--text-secondary)',
        }}>
          <div style={{
            width: 80, height: 80, borderRadius: 20,
            background: 'linear-gradient(135deg, #f59e0b, #d97706)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px', boxShadow: '0 6px 30px rgba(245,158,11,0.25)'
          }}>
            <Wrench size={40} color="#ffffff" />
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
            Select a scan to see your remediation plan
          </div>
          <div style={{ fontSize: 13 }}>Step-by-step actions and legal guidance based on what was found in your file.</div>
        </div>
      )}

      {/* Plan */}
      {plan && !loading && (
        <>
          {/* Summary bar */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20,
          }}>
            {[
              { label: 'Finding Types',     value: plan.total_types,        color: '#60a5fa' },
              { label: 'Need Immediate Action', value: plan.immediate_actions, color: '#f87171' },
              { label: 'Total Steps',       value: plan.total_steps ?? plan.plans?.reduce((a, p) => a + p.steps.length, 0) ?? 0, color: '#4ade80' },
            ].map((s, i) => (
              <div key={i} style={{
                background: 'var(--card)', border: '1px solid var(--border)',
                borderRadius: 12, padding: '14px 16px', textAlign: 'center',
              }}>
                <div style={{ fontSize: 26, fontWeight: 800, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Immediate alert banner */}
          {immediateCount > 0 && (
            <div style={{
              background: 'rgba(248,113,113,0.08)', border: '1.5px solid rgba(248,113,113,0.3)',
              borderRadius: 12, padding: '12px 18px', marginBottom: 16,
              display: 'flex', alignItems: 'center', gap: 10,
              color: '#f87171', fontSize: 13,
            }}>
              <Zap size={16} />
              <strong>{immediateCount} action{immediateCount > 1 ? 's' : ''} require IMMEDIATE attention.</strong>
              &nbsp;Complete the highlighted steps as soon as possible.
            </div>
          )}

          {/* Remediation cards */}
          {plan.plans.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>
              <ShieldCheck size={40} strokeWidth={1.2} style={{ marginBottom: 12 }} />
              <div>No findings to remediate. This scan is clean! ✅</div>
            </div>
          ) : (
            plan.plans.map((p, i) => <RemediationCard key={i} plan={p} index={i} onNavigate={navigate} />)
          )}

        </>
      )}
    </div>
  );
}
