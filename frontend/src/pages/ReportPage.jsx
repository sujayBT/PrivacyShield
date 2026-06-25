import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  getScans, generateReport, generateSensitiveSummary,
  generateMetadataReport, generateAttackSimulation,
  generateScoreHistory, generateBatchReport, generateRemediationReport,
} from '../api';

import { FileText, Download, X, Info, Shield, Database,
  Zap, TrendingUp, Layers, CheckCircle, AlertCircle, Wrench } from 'lucide-react';


const STORAGE_KEY = 'reportPageState';
const riskColor = (r) => ({ CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e' }[r] || '#22c55e');

// ── Report type definitions ──────────────────────────────────────────────────
const REPORT_TYPES = [
  {
    id: 'privacy',
    icon: Shield,
    emoji: '🔒',
    label: 'Privacy Exposure Report',
    desc: 'Full PII analysis: score, all 16 finding types, security recommendations, and extracted OCR text.',
    severity: 'CRITICAL',
    color: '#ef4444',
    bg: 'rgba(239,68,68,0.08)',
    border: 'rgba(239,68,68,0.2)',
    requiresScan: true,
    filename: (s) => `privacy_report_${s?.filename}.pdf`,
    call: (id) => generateReport(id),
  },
  {
    id: 'summary',
    icon: Database,
    emoji: '📊',
    label: 'Sensitive Data Summary',
    desc: 'Categorized breakdown of all detected sensitive data grouped by finding type with counts.',
    severity: 'HIGH',
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.2)',
    requiresScan: true,
    filename: (s) => `sensitive_summary_${s?.filename}.pdf`,
    call: (id) => generateSensitiveSummary(id),
  },
  {
    id: 'metadata',
    icon: FileText,
    emoji: '🗂️',
    label: 'Metadata Report',
    desc: 'Technical metadata: file info, OCR stats, detection method breakdown, Vision AI results.',
    severity: 'MEDIUM',
    color: '#6366f1',
    bg: 'rgba(99,102,241,0.08)',
    border: 'rgba(99,102,241,0.2)',
    requiresScan: true,
    // Only available for file upload scans — not social/batch/URL scans
    fileOnly: true,
    filename: (s) => `metadata_report_${s?.filename}.pdf`,
    call: (id) => generateMetadataReport(id),
  },
  {
    id: 'attack',
    icon: Zap,
    emoji: '⚡',
    label: 'Attack Simulation Report',
    desc: 'Simulated attack vectors showing exactly how an attacker could exploit each piece of exposed data.',
    severity: 'CRITICAL',
    color: '#dc2626',
    bg: 'rgba(220,38,38,0.08)',
    border: 'rgba(220,38,38,0.25)',
    requiresScan: true,
    filename: (s) => `attack_simulation_${s?.filename}.pdf`,
    call: (id) => generateAttackSimulation(id),
  },
  {
    id: 'history',
    icon: TrendingUp,
    emoji: '📈',
    label: 'Score History Report',
    desc: 'Privacy score trend across all your scans with stats, risk distribution, and per-file breakdown.',
    severity: 'LOW',
    color: '#22c55e',
    bg: 'rgba(34,197,94,0.08)',
    border: 'rgba(34,197,94,0.2)',
    requiresScan: false,
    filename: () => 'score_history_report.pdf',
    call: () => generateScoreHistory(),
  },
  {
    id: 'batch',
    icon: Layers,
    emoji: '📋',
    label: 'Batch Scan Report',
    desc: 'Combined report of Batch Screenshot Scanner results only — aggregate stats + per-screenshot findings table.',
    subtitle: '✓ Batch Screenshot Scanner only',
    subtitleColor: '#14b8a6',
    severity: 'MEDIUM',
    color: '#14b8a6',
    bg: 'rgba(20,184,166,0.08)',
    border: 'rgba(20,184,166,0.2)',
    requiresScan: false,
    filename: () => 'batch_scan_report.pdf',
    call: () => generateBatchReport(),
  },
  {
    id: 'remediation',
    icon: Wrench,
    emoji: '🔧',
    label: 'Remediation Action Plan',
    desc: 'Printable step-by-step fix guide — cover page, urgency levels, legal references, and all action steps per finding type.',
    severity: 'HIGH',
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.2)',
    requiresScan: true,
    filename: (s) => `remediation_plan_${s?.filename}.pdf`,
    call: (id) => generateRemediationReport(id),
  },
];


// ── Download helper ───────────────────────────────────────────────────────────
const triggerDownload = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
};

export default function ReportPage() {
  const [scans, setScans] = useState([]);
  const [searchParams] = useSearchParams();
  const defaultId = searchParams.get('id');

  const [selected, setSelected] = useState(() => {
    if (defaultId) return defaultId;
    try { return localStorage.getItem(STORAGE_KEY) || ''; } catch { return ''; }
  });

  const [loadingId, setLoadingId] = useState(null); // which report type is generating
  const [statuses, setStatuses] = useState({});     // {reportId: 'success'|'error'|msg}

  const persistSelected = useCallback((id) => {
    setSelected(id);
    try { if (id) localStorage.setItem(STORAGE_KEY, id); else localStorage.removeItem(STORAGE_KEY); } catch {}
  }, []);

  useEffect(() => { getScans().then(setScans); }, []);
  useEffect(() => { if (defaultId) persistSelected(defaultId); }, [defaultId]);

  const scan = selected ? scans.find(s => s.id === Number(selected)) : null;

  const handleDownload = async (rtype) => {
    const needsScan = rtype.requiresScan;
    if (needsScan && !scan) return;

    setLoadingId(rtype.id);
    setStatuses(prev => ({ ...prev, [rtype.id]: null }));

    try {
      const blob = await rtype.call(scan?.id);
      triggerDownload(blob, rtype.filename(scan));
      setStatuses(prev => ({ ...prev, [rtype.id]: 'success' }));
      setTimeout(() => setStatuses(prev => ({ ...prev, [rtype.id]: null })), 3500);
    } catch (e) {
      // Friendly message for metadata on non-file scans
      let msg = e.response?.data?.detail || e.message || 'Failed';
      if (rtype.id === 'metadata' && (msg.includes('Network') || msg.includes('500') || msg.includes('502'))) {
        msg = 'Metadata not available for this scan type. Select a file upload scan.';
      }
      setStatuses(prev => ({ ...prev, [rtype.id]: `error:${msg}` }));
    } finally { setLoadingId(null); }
  };

  const handleClear = () => { persistSelected(''); setStatuses({}); };

  const byType = (type) => scan?.findings?.filter(f => f.type === type).length || 0;
  const totalFindings = scan?.findings?.length || 0;

  return (
    <div>
      {/* Top Control Bar */}
      <div className="card" style={{ padding: '20px 24px', marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
          <div className="section-title" style={{ margin: 0 }}>
            <FileText size={16} color="var(--accent)" /> Report Generator
          </div>
          {scan && (
            <button className="btn btn-danger btn-sm" onClick={handleClear}>
              <X size={13} /> Clear
            </button>
          )}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
          Generate 6 types of PDF reports. Select a scan for per-file reports. History & Batch reports use all your scans.
        </p>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <select className="input" style={{ maxWidth: 420, flex: '1 1 260px' }}
            value={selected} onChange={e => persistSelected(e.target.value)}>
            <option value="">— Select a scan (for per-file reports) —</option>
            {scans.map(s => (
              <option key={s.id} value={s.id}>
                #{s.id} — {s.filename} [{s.risk_level}] Score: {Math.round(s.score)}
              </option>
            ))}
          </select>
          {scan && (
            <span style={{
              fontSize: 11, fontWeight: 700, padding: '4px 10px',
              borderRadius: 12, background: `${riskColor(scan.risk_level)}18`,
              color: riskColor(scan.risk_level), border: `1px solid ${riskColor(scan.risk_level)}44`
            }}>
              {scan.risk_level} — Score {Math.round(scan.score)} — {totalFindings} findings
            </span>
          )}
        </div>
      </div>

      {/* Scan stat mini-cards (shown when scan selected) */}
      {scan && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px,1fr))', gap: 10, marginBottom: 20 }}>
          {[
            { label: 'Score',    value: Math.round(scan.score), color: riskColor(scan.risk_level) },
            { label: 'Passwords', value: byType('password') },
            { label: 'Aadhaar',   value: byType('aadhaar') },
            { label: 'PAN',       value: byType('pan_card') },
            { label: 'CC/CVV',    value: byType('credit_card') + byType('cvv') },
            { label: 'Emails',    value: byType('email') },
            { label: 'Phones',    value: byType('phone') },
            { label: 'OTP',       value: byType('otp') },
            { label: 'Faces',     value: byType('face_detected') },
            { label: 'ID Card',   value: byType('id_card_visible') },
          ].map((item, i) => (
            <div key={i} style={{
              background: 'var(--bg-card)', borderRadius: 10,
              border: '1px solid var(--border)', padding: '10px 14px', textAlign: 'center'
            }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: item.color || 'var(--text-primary)', lineHeight: 1 }}>
                {item.value}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Report Type Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(310px,1fr))', gap: 16 }}>
        {REPORT_TYPES.map(rtype => {
          const Icon = rtype.icon;
          const isLoading = loadingId === rtype.id;
          const status = statuses[rtype.id];
          const isSuccess = status === 'success';
          const isError = status?.startsWith('error:');
          const errMsg = isError ? status.replace('error:','') : '';

          // Metadata is only for file-upload scans, not social/batch/URL
          const isNonFileSource = scan && rtype.fileOnly &&
            (scan.source?.startsWith('social_') || scan.source?.startsWith('batch') ||
             scan.source?.startsWith('url') || scan.source?.startsWith('cloud'));
          const disabled = (rtype.requiresScan && !scan) || isNonFileSource;

          return (
            <div key={rtype.id} className="card" style={{
              padding: 0, overflow: 'hidden',
              border: `1px solid ${disabled ? 'var(--border)' : rtype.border}`,
              opacity: disabled ? 0.55 : 1,
              transition: 'transform 0.15s, box-shadow 0.15s',
            }}>
              {/* Card header */}
              <div style={{
                padding: '14px 18px',
                background: disabled ? 'transparent' : rtype.bg,
                borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <div style={{
                  width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                  background: disabled ? 'var(--bg-base)' : rtype.bg,
                  border: `1px solid ${disabled ? 'var(--border)' : rtype.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18,
                }}>{rtype.emoji}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: disabled ? 'var(--text-secondary)' : 'var(--text-primary)', lineHeight: 1.3 }}>
                    {rtype.label}
                  </div>
                  {rtype.requiresScan && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                      {disabled && !isNonFileSource ? '⚠ Select a scan first'
                        : isNonFileSource ? '⚠ File upload scans only'
                        : `✓ Ready: ${scan?.filename}`}
                    </div>
                  )}
                  {!rtype.requiresScan && (
                    <div style={{ fontSize: 10, color: rtype.subtitleColor || '#22c55e', marginTop: 2 }}>
                      {rtype.subtitle || '✓ Uses all your scans'}
                    </div>
                  )}
                </div>
              </div>

              {/* Card body */}
              <div style={{ padding: '14px 18px' }}>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 14 }}>
                  {rtype.desc}
                </p>

                {/* Status messages */}
                {isSuccess && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12,
                    color: '#22c55e', background: 'rgba(34,197,94,0.08)',
                    border: '1px solid rgba(34,197,94,0.2)', borderRadius: 6, padding: '6px 10px', marginBottom: 10 }}>
                    <CheckCircle size={13} /> Downloaded successfully!
                  </div>
                )}
                {isError && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12,
                    color: '#ef4444', background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, padding: '6px 10px', marginBottom: 10 }}>
                    <AlertCircle size={13} /> {errMsg}
                  </div>
                )}

                <button
                  className="btn btn-primary"
                  style={{ width: '100%', background: disabled ? undefined : rtype.color, borderColor: disabled ? undefined : rtype.color }}
                  disabled={disabled || !!loadingId}
                  onClick={() => handleDownload(rtype)}
                >
                  {isLoading
                    ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Generating...</>
                    : <><Download size={13} /> Download PDF</>}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {scans.length === 0 && (
        <div className="card" style={{ padding: 64, textAlign: 'center', color: 'var(--text-secondary)', marginTop: 20 }}>
          <div style={{ fontSize: 52, marginBottom: 16 }}>📄</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>No scans yet</div>
          <div style={{ fontSize: 13 }}>Upload and scan a document first to generate reports.</div>
        </div>
      )}
    </div>
  );
}
