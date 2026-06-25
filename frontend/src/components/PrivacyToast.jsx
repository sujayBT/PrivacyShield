import React, { useEffect, useState } from 'react';
import { ShieldAlert, ShieldCheck, ShieldX, X, ExternalLink, ChevronRight } from 'lucide-react';

// ── Risk configuration ────────────────────────────────────────────────────────
const RISK_CFG = {
  CRITICAL: {
    accent:    '#ef4444',
    accentDim: 'rgba(239,68,68,0.12)',
    border:    'rgba(239,68,68,0.35)',
    badge:     '#7f1d1d',
    badgeText: '#fca5a5',
    label:     'Critical Risk',
    icon:      ShieldX,
    timeout:   0,           // stays until dismissed
  },
  HIGH: {
    accent:    '#f97316',
    accentDim: 'rgba(249,115,22,0.10)',
    border:    'rgba(249,115,22,0.30)',
    badge:     '#7c2d12',
    badgeText: '#fdba74',
    label:     'High Risk',
    icon:      ShieldAlert,
    timeout:   14000,
  },
  MEDIUM: {
    accent:    '#eab308',
    accentDim: 'rgba(234,179,8,0.09)',
    border:    'rgba(234,179,8,0.28)',
    badge:     '#713f12',
    badgeText: '#fde047',
    label:     'Medium Risk',
    icon:      ShieldAlert,
    timeout:   9000,
  },
};

// ── Friendly labels for finding types ────────────────────────────────────────
const TYPE_LABELS = {
  email:           'Email Address',
  phone:           'Phone Number',
  aadhaar:         'Aadhaar Number',
  pan:             'PAN Card',
  credit_card:     'Credit Card',
  password:        'Password',
  otp:             'OTP / PIN',
  face_detected:   'Face Detected',
  dob:             'Date of Birth',
  location:        'Location',
  person_name:     'Person Name',
  bank_account:    'Bank Account',
};

const TYPE_ICONS = {
  email: '📧', phone: '📱', aadhaar: '🪪', pan: '🪪',
  credit_card: '💳', password: '🔑', otp: '🔒',
  face_detected: '👤', dob: '📅', location: '📍',
  person_name: '👤', bank_account: '🏦',
};

// ── Individual Toast card ─────────────────────────────────────────────────────
function Toast({ toast, onDismiss }) {
  const cfg = RISK_CFG[toast.risk] || RISK_CFG.MEDIUM;
  const Icon = cfg.icon;
  const [progress, setProgress] = useState(100);
  const [visible,  setVisible]  = useState(false);

  // Fade in
  useEffect(() => { const t = setTimeout(() => setVisible(true), 30); return () => clearTimeout(t); }, []);

  // Auto-dismiss countdown
  useEffect(() => {
    if (!cfg.timeout) return;
    const start = Date.now();
    const timer = setInterval(() => {
      const pct = 100 - ((Date.now() - start) / cfg.timeout) * 100;
      if (pct <= 0) { handleDismiss(); clearInterval(timer); }
      else setProgress(pct);
    }, 50);
    return () => clearInterval(timer);
  }, []);

  const handleDismiss = () => {
    setVisible(false);
    setTimeout(() => onDismiss(toast.id), 260);
  };

  // Top 3 findings only, formatted nicely
  const findings = (toast.types || []).slice(0, 3);
  const extra    = (toast.types || []).length - 3;

  return (
    <div style={{
      width: 340,
      background: 'linear-gradient(145deg, #16172b, #1a1b30)',
      border: `1px solid ${cfg.border}`,
      borderRadius: 14,
      boxShadow: `0 12px 40px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04), inset 0 1px 0 rgba(255,255,255,0.06)`,
      overflow: 'hidden',
      transform: visible ? 'translateX(0) scale(1)' : 'translateX(360px) scale(0.96)',
      opacity: visible ? 1 : 0,
      transition: 'transform 0.28s cubic-bezier(0.34,1.56,0.64,1), opacity 0.25s ease',
    }}>

      {/* ── Top accent strip ── */}
      <div style={{ height: 3, background: `linear-gradient(90deg, ${cfg.accent}, ${cfg.accent}88)` }} />

      {/* ── Header ── */}
      <div style={{
        padding: '12px 14px 10px',
        display: 'flex', alignItems: 'center', gap: 10,
        borderBottom: `1px solid rgba(255,255,255,0.06)`,
        background: cfg.accentDim,
      }}>
        {/* Shield icon */}
        <div style={{
          width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
          background: `radial-gradient(circle, ${cfg.accentDim}, transparent)`,
          border: `1.5px solid ${cfg.accent}55`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={17} color={cfg.accent} strokeWidth={2} />
        </div>

        {/* Title + subtitle */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
            color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', marginBottom: 1,
          }}>
            Privacy Protection Monitor
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              fontSize: 12, fontWeight: 800, color: cfg.accent,
            }}>{cfg.label}</span>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
              background: cfg.badge + '55', color: cfg.badgeText,
              border: `1px solid ${cfg.accent}40`,
            }}>
              {toast.score}/100
            </span>
          </div>
        </div>

        {/* Dismiss X */}
        <button onClick={handleDismiss} style={{
          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 6, width: 24, height: 24, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'rgba(255,255,255,0.45)', flexShrink: 0,
          transition: 'background 0.15s, color 0.15s',
        }}
          onMouseEnter={e => { e.target.closest('button').style.background = 'rgba(255,255,255,0.12)'; e.target.closest('button').style.color = '#fff'; }}
          onMouseLeave={e => { e.target.closest('button').style.background = 'rgba(255,255,255,0.06)'; e.target.closest('button').style.color = 'rgba(255,255,255,0.45)'; }}
        >
          <X size={12} strokeWidth={2.5} />
        </button>
      </div>

      {/* ── Body ── */}
      <div style={{ padding: '12px 14px' }}>

        {/* Detected items label */}
        {findings.length > 0 && (
          <>
            <div style={{
              fontSize: 10, fontWeight: 600, letterSpacing: '0.07em',
              color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', marginBottom: 8,
            }}>
              Detected
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 12 }}>
              {findings.map(t => (
                <div key={t} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '5px 9px', borderRadius: 7,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.07)',
                }}>
                  <span style={{ fontSize: 13, lineHeight: 1 }}>{TYPE_ICONS[t] || '⚠️'}</span>
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.80)', fontWeight: 500 }}>
                    {TYPE_LABELS[t] || t}
                  </span>
                  <ChevronRight size={11} color="rgba(255,255,255,0.2)" style={{ marginLeft: 'auto' }} />
                </div>
              ))}
              {extra > 0 && (
                <div style={{
                  fontSize: 11, color: 'rgba(255,255,255,0.35)',
                  padding: '3px 9px', fontStyle: 'italic',
                }}>
                  +{extra} more detected
                </div>
              )}
            </div>
          </>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 7 }}>
          {toast.scanId && (
            <button
              onClick={() => { window.location.href = `/recommendations?id=${toast.scanId}`; handleDismiss(); }}
              style={{
                flex: 1, padding: '7px 10px', borderRadius: 8, border: 'none',
                background: `linear-gradient(135deg, ${cfg.accent}, ${cfg.accent}cc)`,
                color: '#fff', fontWeight: 700, fontSize: 11, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                boxShadow: `0 3px 10px ${cfg.accent}44`,
                transition: 'opacity 0.15s, transform 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.opacity = '0.88'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              <ExternalLink size={11} strokeWidth={2.5} />
              View Details
            </button>
          )}
          <button
            onClick={handleDismiss}
            style={{
              flex: toast.scanId ? '0 0 auto' : 1,
              padding: '7px 12px', borderRadius: 8, cursor: 'pointer',
              background: 'rgba(255,255,255,0.07)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: 'rgba(255,255,255,0.60)', fontWeight: 600, fontSize: 11,
              transition: 'background 0.15s, color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = '#fff'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'rgba(255,255,255,0.60)'; }}
          >
            Dismiss
          </button>
        </div>
      </div>

      {/* ── Auto-dismiss progress bar ── */}
      {cfg.timeout > 0 && (
        <div style={{ height: 2, background: 'rgba(255,255,255,0.06)' }}>
          <div style={{
            height: '100%', width: `${progress}%`,
            background: `linear-gradient(90deg, ${cfg.accent}99, ${cfg.accent})`,
            transition: 'width 0.05s linear',
            borderRadius: '0 0 0 0',
          }} />
        </div>
      )}
    </div>
  );
}

// ── Container — positions all toasts in fixed bottom-right ───────────────────
export default function PrivacyToastContainer({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      right: 24,
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column-reverse',
      gap: 10,
      pointerEvents: 'none',
      maxWidth: 360,
    }}>
      {toasts.map(t => (
        <div key={t.id} style={{ pointerEvents: 'all' }}>
          <Toast toast={t} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}
