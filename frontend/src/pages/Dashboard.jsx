import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getScans, getAiInfo } from '../api';
import { useAuth } from '../context/AuthContext';
import { TrendingUp, Clock, AlertCircle, ChevronRight, ShieldCheck, ShieldAlert, Shield } from 'lucide-react';

const QUICK_ACTIONS = [
  {
    icon: '📤', title: 'Upload & Scan', desc: 'Detect PII in any file', route: '/scan',
    color: 'rgba(32,101,209,0.08)', border: 'rgba(32,101,209,0.2)', iconBg: 'rgba(32,101,209,0.12)'
  },
  {
    icon: '🔵', title: 'Blur Engine', desc: 'Redact sensitive areas', route: '/blur',
    color: 'rgba(124,58,237,0.08)', border: 'rgba(124,58,237,0.2)', iconBg: 'rgba(124,58,237,0.12)'
  },
  {
    icon: '📄', title: 'Generate Report', desc: 'Export PDF analysis', route: '/report',
    color: 'rgba(34,197,94,0.08)', border: 'rgba(34,197,94,0.2)', iconBg: 'rgba(34,197,94,0.12)'
  },
  {
    icon: '💡', title: 'Recommendations', desc: 'Get security tips', route: '/recommendations',
    color: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', iconBg: 'rgba(245,158,11,0.12)'
  },
];

const RiskBadge = ({ risk }) => (
  <span className={`badge badge-${(risk || 'low').toLowerCase()}`}>{risk || 'LOW'}</span>
);

export default function Dashboard() {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [aiInfo, setAiInfo] = useState(null);
  const { username } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    getScans().then(d => { setScans(d); setLoading(false); }).catch(() => setLoading(false));
    getAiInfo().then(setAiInfo).catch(() => { });
  }, []);

  const totalScans  = scans.length;
  const criticalHigh = scans.filter(s => s.risk_level === 'CRITICAL' || s.risk_level === 'HIGH').length;
  const medium       = scans.filter(s => s.risk_level === 'MEDIUM').length;
  const avgScore     = totalScans ? Math.round(scans.reduce((a, s) => a + s.score, 0) / totalScans) : 0;
  const lowSafe      = scans.filter(s => s.risk_level === 'LOW' || s.risk_level === 'SAFE').length;
  const recentScans  = scans.slice(0, 6);


  return (
    <div>
      {/* Hero Banner */}
      <div className="hero-banner animate-up">
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <div className="hero-status"><div className="hero-dot" /> PROTECTED</div>
            {aiInfo?.available && (
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                fontSize: 11, fontWeight: 700, letterSpacing: '0.04em',
                color: '#06b6d4', background: 'rgba(6,182,212,0.12)',
                border: '1px solid rgba(6,182,212,0.3)',
                borderRadius: 20, padding: '3px 10px',
              }}>🤖 spaCy AI Active — {aiInfo.model}</div>
            )}
          </div>
          <h1 className="hero-title">You are protected ✓</h1>
          <p className="hero-subtitle">
            Welcome back, <strong>{username}</strong>. Your privacy intelligence dashboard is ready —
            upload documents, detect sensitive data, and secure your digital footprint.
          </p>
        </div>
        <div style={{ position: 'absolute', right: 40, top: '50%', transform: 'translateY(-50%)', opacity: 0.18, userSelect: 'none' }} className="animate-float">
          <img src="/app_logo.png" alt="" style={{ width: 90, height: 90, borderRadius: 22, objectFit: 'cover', filter: 'drop-shadow(0 0 24px rgba(0,180,255,0.5))' }} />
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        {[
          { icon: '📂', label: 'Total Scans',        value: totalScans,   color: 'rgba(32,101,209,0.1)',  tcolor: 'var(--accent)'   },
          { icon: '🚨', label: 'Critical / High',     value: criticalHigh, color: 'rgba(239,68,68,0.1)',   tcolor: 'var(--danger)'   },
          { icon: '⚠️', label: 'Medium Risk Files',   value: medium,       color: 'rgba(245,158,11,0.1)',  tcolor: 'var(--warning)'  },
          { icon: '✅', label: 'Low / Safe Files',    value: lowSafe,      color: 'rgba(34,197,94,0.1)',   tcolor: 'var(--success)'  },
        ].map((s, i) => (
          <div key={i} className={`stat-card card animate-up-${i + 1}`}>
            <div className="stat-card-icon" style={{ background: s.color }}>
              <span style={{ fontSize: 20 }}>{s.icon}</span>
            </div>
            <div className="stat-card-value" style={{ color: s.tcolor }}>{s.value}</div>
            <div className="stat-card-label">{s.label}</div>
          </div>
        ))}
      </div>


      {/* Quick Actions */}
      <div className="section-title animate-up-2">
        <TrendingUp size={16} style={{ color: 'var(--accent)' }} /> Quick Actions
      </div>
      <div className="quick-actions animate-up-2">
        {QUICK_ACTIONS.map((qa, i) => (
          <div key={i} className="quick-action-card"
            style={{ borderColor: qa.border, background: qa.color }}
            onClick={() => navigate(qa.route)}>
            <div className="qa-icon" style={{ background: qa.iconBg }}>
              <span>{qa.icon}</span>
            </div>
            <div className="qa-title">{qa.title}</div>
            <div className="qa-desc">{qa.desc}</div>
            <div className="qa-arrow">Go <ChevronRight size={12} /></div>
          </div>
        ))}
      </div>

      {/* Recent Scans */}
      <div className="card animate-up-3">
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="section-title" style={{ margin: 0 }}>
            <Clock size={15} style={{ color: 'var(--accent)' }} /> Recent Scans
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/scan')}>+ New Scan</button>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto', borderColor: 'var(--border)', borderTopColor: 'var(--accent)', width: 28, height: 28, borderWidth: 3 }} />
          </div>
        ) : recentScans.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>
            <AlertCircle size={36} style={{ marginBottom: 12, opacity: 0.3, display: 'block', margin: '0 auto 12px' }} />
            <p style={{ fontWeight: 600, marginBottom: 6 }}>No scans yet</p>
            <p style={{ fontSize: 13 }}>Upload your first document to see results here.</p>
            <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/scan')}>Upload & Scan</button>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>#</th><th>Filename</th><th>Date</th>
                  <th>Score</th><th>Risk</th><th>Findings</th><th></th>
                </tr>
              </thead>
              <tbody>
                {recentScans.map(scan => (
                  <tr key={scan.id}>
                    <td style={{ color: 'var(--text-muted)', fontWeight: 600, fontSize: 12 }}>#{scan.id}</td>
                    <td style={{ fontWeight: 600 }}>{scan.filename}</td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{new Date(scan.upload_date).toLocaleString()}</td>
                    <td>
                      <span style={{
                        fontWeight: 800, fontSize: 16,
                        color: scan.score >= 50 ? 'var(--danger)' : scan.score >= 20 ? 'var(--warning)' : 'var(--success)'
                      }}>
                        {Math.round(scan.score)}
                      </span>
                    </td>
                    <td><RiskBadge risk={scan.risk_level} /></td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{scan.findings?.length || 0} items</td>
                    <td>
                      <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/scan?id=${scan.id}`)}>
                        Details →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
