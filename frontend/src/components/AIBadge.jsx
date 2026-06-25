import React from 'react';

/**
 * AIBadge — shows the AI confidence score for a single finding.
 *
 * Props:
 *   confidence: float 0.0–1.0
 *   label: "HIGH_CONFIDENCE" | "MEDIUM_CONFIDENCE" | "LOW_CONFIDENCE"
 *   small: bool — compact mode for inline use
 */
const AIBadge = ({ confidence, label, small = false }) => {
  if (confidence == null) return null;

  const pct = Math.round(confidence * 100);

  const cfg =
    pct >= 75 ? { color: '#22c55e', bg: 'rgba(34,197,94,0.10)',  border: 'rgba(34,197,94,0.25)',  text: 'High' } :
    pct >= 45 ? { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.25)', text: 'Med' } :
                { color: '#ef4444', bg: 'rgba(239,68,68,0.10)',  border: 'rgba(239,68,68,0.25)',  text: 'Low' };

  if (small) {
    return (
      <span
        title={`AI Confidence: ${pct}% (${label?.replace('_CONFIDENCE', '') ?? ''})`}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 3,
          fontSize: 10, fontWeight: 700, letterSpacing: '0.02em',
          color: cfg.color,
          background: cfg.bg,
          border: `1px solid ${cfg.border}`,
          borderRadius: 5, padding: '1px 5px',
          lineHeight: 1.4, flexShrink: 0,
        }}
      >
        🤖 {pct}%
      </span>
    );
  }

  return (
    <div
      title={`AI Confidence: ${pct}%`}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        fontSize: 11, fontWeight: 600,
        color: cfg.color,
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
        borderRadius: 6, padding: '3px 8px',
      }}
    >
      <span style={{ fontSize: 12 }}>🤖</span>
      <span>AI {cfg.text} · {pct}%</span>
      {/* Mini confidence bar */}
      <span style={{
        display: 'inline-block', width: 32, height: 4,
        background: 'rgba(0,0,0,0.1)', borderRadius: 2, overflow: 'hidden',
      }}>
        <span style={{
          display: 'block', height: '100%',
          width: `${pct}%`, background: cfg.color,
          borderRadius: 2, transition: 'width 0.6s ease',
        }} />
      </span>
    </div>
  );
};

export default AIBadge;
