import React, { useState, useEffect, useCallback } from 'react';
import { scanUrl, getUrlScanHistory, deleteUrlScan } from '../api';
import { Globe, Search, X, Clock, AlertCircle, ExternalLink, CheckCircle,
  Mail, Phone, Key, CreditCard, Fingerprint, Calendar, Hash,
  MessageSquare, User, MapPin, Building2, DollarSign, Shield } from 'lucide-react';
import AIBadge from '../components/AIBadge';

const riskColor = (r) => ({ CRITICAL: '#dc2626', HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e', SAFE: '#22c55e' }[r] || '#22c55e');
const riskBg   = (r) => ({ CRITICAL: 'rgba(220,38,38,0.1)', HIGH: 'rgba(239,68,68,0.1)', MEDIUM: 'rgba(245,158,11,0.1)', LOW: 'rgba(34,197,94,0.1)', SAFE: 'rgba(34,197,94,0.1)' }[r] || 'rgba(34,197,94,0.1)');

const SAMPLE_URLS = [
  // Confirmed working — tested live
  { label: '📧 MIT contact (emails)',         url: 'https://www.mit.edu/contact/' },
  { label: '📧 W3Schools about (emails)',     url: 'https://www.w3schools.com/about/' },
  { label: '🔧 JSONPlaceholder /users (JSON)', url: 'https://jsonplaceholder.typicode.com/users' },
  { label: '🔧 GitHub API (JSON)',             url: 'https://api.github.com' },
  { label: '🌐 Wikipedia: Privacy',            url: 'https://en.wikipedia.org/wiki/Privacy' },
  { label: '🌐 HaveIBeenPwned',                url: 'https://haveibeenpwned.com' },
  { label: '🌐 DuckDuckGo Privacy',            url: 'https://duckduckgo.com/privacy' },
];

const FINDING_TYPES = [
  { type: 'http_only',    label: 'Connection Security', icon: AlertCircle, color: '#ef4444', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.3)' },
  { type: 'password',     label: 'Passwords',     icon: Key,         color: '#dc2626', bg: 'rgba(220,38,38,0.1)',   border: 'rgba(220,38,38,0.3)'   },
  { type: 'aadhaar',     label: 'Aadhaar IDs',   icon: Fingerprint, color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.3)'   },
  { type: 'pan_card',    label: 'PAN Cards',     icon: CreditCard,  color: '#b91c1c', bg: 'rgba(185,28,28,0.1)',   border: 'rgba(185,28,28,0.3)'   },
  { type: 'credit_card', label: 'Credit Cards',  icon: CreditCard,  color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)'  },
  { type: 'cvv',         label: 'CVV Codes',     icon: Hash,        color: '#d97706', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.25)' },
  { type: 'otp',         label: 'OTPs',          icon: MessageSquare, color: '#b45309', bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.2)'  },
  { type: 'dob',         label: 'Date of Birth', icon: Calendar,    color: '#7c3aed', bg: 'rgba(124,58,237,0.1)',  border: 'rgba(124,58,237,0.3)'  },
  { type: 'email',       label: 'Emails',        icon: Mail,        color: '#2065d1', bg: 'rgba(32,101,209,0.1)',  border: 'rgba(32,101,209,0.25)' },
  { type: 'phone',       label: 'Phone Numbers', icon: Phone,       color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   border: 'rgba(34,197,94,0.25)'  },
  { type: 'person_name', label: 'Person Names',  icon: User,        color: '#06b6d4', bg: 'rgba(6,182,212,0.1)',   border: 'rgba(6,182,212,0.3)'   },
  { type: 'location',    label: 'Locations',     icon: MapPin,      color: '#14b8a6', bg: 'rgba(20,184,166,0.1)',  border: 'rgba(20,184,166,0.3)'  },
  { type: 'organization',label: 'Organizations', icon: Building2,   color: '#6366f1', bg: 'rgba(99,102,241,0.1)',  border: 'rgba(99,102,241,0.3)'  },
  { type: 'financial',   label: 'Financial Data',icon: DollarSign,  color: '#eab308', bg: 'rgba(234,179,8,0.1)',   border: 'rgba(234,179,8,0.3)'   },
];

const ScoreRing = ({ score, risk }) => {
  const color = riskColor(risk);
  const r = 44; const circ = 2 * Math.PI * r;
  const offset = circ - (Math.min(score, 100) / 100) * circ;
  return (
    <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 106, height: 106 }}>
      <svg width="106" height="106" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="53" cy="53" r={r} fill="none" stroke="var(--border)" strokeWidth="8" />
        <circle cx="53" cy="53" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circ} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1s ease', strokeLinecap: 'round' }} />
      </svg>
      <div style={{ position: 'absolute', textAlign: 'center' }}>
        <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1, color }}>{Math.round(score)}</div>
        <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>/ 100</div>
      </div>
    </div>
  );
};

export default function URLScanPage() {
  const [url, setUrl] = useState('');
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [deletingId, setDeletingId] = useState(null);

  const loadHistory = useCallback(async () => {
    try {
      const h = await getUrlScanHistory();
      setHistory(h);
    } catch (e) {
      console.error('History load failed', e);
    } finally { setLoadingHistory(false); }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const handleScan = async () => {
    const trimmed = url.trim();
    if (!trimmed) return;
    setScanning(true);
    setError('');
    setResult(null);
    try {
      const data = await scanUrl(trimmed);
      setResult(data);
      loadHistory(); // refresh history
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Scan failed';
      setError(msg);
    } finally { setScanning(false); }
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter') handleScan(); };
  const handleClear = () => { setResult(null); setError(''); setUrl(''); };

  const handleDelete = async (e, scanId) => {
    e.stopPropagation();
    if (deletingId) return;
    setDeletingId(scanId);
    try {
      await deleteUrlScan(scanId);
      setHistory(h => h.filter(s => s.id !== scanId));
    } catch (err) {
      console.error('Delete failed', err);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div>
      {/* URL Input Card */}
      <div className="card" style={{ padding: '20px 24px', marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <div className="section-title" style={{ margin: 0 }}>
            <Globe size={16} color="var(--accent)" /> URL Scanner
          </div>
          {result && (
            <button className="btn btn-danger btn-sm" onClick={handleClear}>
              <X size={13} /> Clear
            </button>
          )}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
          Scan any public webpage or online PDF for exposed sensitive data. Powered by regex + AI NER.
        </p>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: '1 1 340px' }}>
            <Globe size={15} style={{
              position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
              color: 'var(--text-muted)', pointerEvents: 'none'
            }} />
            <input
              className="input"
              style={{ paddingLeft: 36, width: '100%' }}
              placeholder="https://example.com or paste any URL…"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={scanning}
            />
          </div>
          <button
            className="btn btn-primary"
            style={{ minWidth: 140 }}
            onClick={handleScan}
            disabled={scanning || !url.trim()}
          >
            {scanning
              ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Scanning…</>
              : <><Search size={14} /> Scan URL</>}
          </button>
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginTop: 14, marginBottom: 0 }}>
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* Sample URLs */}
        {!result && !scanning && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>
              Try:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {SAMPLE_URLS.map((s, i) => (
                <button key={i} onClick={() => { setUrl(s.url); setError(''); }}
                  style={{
                    background: 'var(--bg-base)', border: '1px solid var(--border)',
                    borderRadius: 20, padding: '3px 10px', fontSize: 11, cursor: 'pointer',
                    color: 'var(--text-secondary)', fontWeight: 500,
                    transition: 'all 0.15s', whiteSpace: 'nowrap',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
                  title={s.url}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>


      {/* Results */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
          {/* Left: Score + summary */}
          <div className="card" style={{ padding: 24 }}>
            <div className="section-title"><Shield size={15} color="var(--accent)" /> Scan Results</div>

            {/* URL info */}
            <div style={{ marginBottom: 16, padding: '12px 16px', background: 'var(--bg-base)', borderRadius: 10, border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>SCANNED URL</div>
                {result.url.startsWith('http://') ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, background: 'rgba(220,38,38,0.08)', color: '#ef4444', border: '1px solid rgba(220,38,38,0.2)' }}>
                    <AlertCircle size={10} /> Unsecure HTTP
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, background: 'rgba(34,197,94,0.08)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }}>
                    <Shield size={10} /> Secure HTTPS
                  </span>
                )}
              </div>
              <a href={result.url} target="_blank" rel="noreferrer" style={{
                fontSize: 13, fontWeight: 600, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 5,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
              }}>
                {result.url} <ExternalLink size={12} />
              </a>
              {result.title && (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic' }}>{result.title}</div>
              )}
            </div>

            {/* Score + risk */}
            <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
              <ScoreRing score={result.score} risk={result.risk_level} />
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6 }}>Risk Level</div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 800,
                  background: riskBg(result.risk_level), color: riskColor(result.risk_level),
                  border: `1px solid ${riskColor(result.risk_level)}44`
                }}>
                  {result.risk_level === 'CRITICAL' ? '🔴' : result.risk_level === 'HIGH' ? '🟠' : result.risk_level === 'MEDIUM' ? '🟡' : '🟢'}
                  {result.risk_level}
                </span>
                <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-secondary)' }}>
                  <strong style={{ color: 'var(--text-primary)' }}>{result.finding_count}</strong> sensitive item(s) found
                </div>
                <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>
                  Engine: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{result.ai_engine}</span>
                </div>
              </div>
            </div>

            {/* Extracted text preview */}
            {result.extracted_text_preview && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
                  Text Preview (first 400 chars)
                </div>
                <pre style={{
                  fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-base)',
                  border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 120, overflowY: 'auto', lineHeight: 1.6
                }}>
                  {result.extracted_text_preview}
                </pre>
              </div>
            )}
          </div>

          {/* Right: Findings */}
          <div className="card" style={{ padding: 24 }}>
            <div className="section-title" style={{ marginBottom: 12 }}>
              🔍 Detected Findings
              {result.finding_count > 0 && (
                <span style={{ marginLeft: 8, background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 5, padding: '1px 7px', fontSize: 11, fontWeight: 700 }}>
                  {result.finding_count}
                </span>
              )}
            </div>

            {result.findings?.length > 0 ? (
              <div style={{ maxHeight: 340, overflowY: 'auto' }}>
                {FINDING_TYPES
                  .map(ft => ({ ...ft, items: result.findings.filter(f => f.type === ft.type) }))
                  .filter(g => g.items.length > 0)
                  .map(group => {
                    const Icon = group.icon;
                    const avgConf = group.items.map(f => f.ai_confidence).filter(c => c != null)
                      .reduce((s, c, _, arr) => s + c / arr.length, 0);
                    return (
                      <div key={group.type} style={{ marginBottom: 14 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: group.color, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Icon size={11} /> {group.label} ({group.items.length})
                          {avgConf > 0 && <AIBadge confidence={avgConf} small />}
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                          {group.items.map((f, i) => (
                            <span key={i} className="finding-tag" style={{ background: group.bg, color: group.color, border: `1px solid ${group.border}`, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                              <Icon size={10} />
                              <span style={{ maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.value}</span>
                              {f.ai_confidence != null && <span style={{ fontSize: 9, opacity: 0.7 }}>{Math.round(f.ai_confidence * 100)}%</span>}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })
                }
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '32px 20px' }}>
                <CheckCircle size={36} color="#22c55e" style={{ marginBottom: 10 }} />
                <div style={{ color: '#22c55e', fontWeight: 700, fontSize: 15, marginBottom: 4 }}>All Clear — No PII Detected</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  No sensitive data, phone numbers, emails, or ID patterns were found on this page.
                </div>
              </div>
            )}

          </div>
        </div>
      )}

      {/* Scan History */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Clock size={15} style={{ color: 'var(--accent)' }} />
          <span className="section-title" style={{ margin: 0 }}>URL Scan History</span>
        </div>

        {loadingHistory ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto', borderColor: 'var(--border)', borderTopColor: 'var(--accent)', width: 28, height: 28, borderWidth: 3 }} />
          </div>
        ) : history.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>
            <Globe size={36} style={{ marginBottom: 12, opacity: 0.25, display: 'block', margin: '0 auto 12px' }} />
            <p style={{ fontWeight: 600, marginBottom: 6 }}>No URL scans yet</p>
            <p style={{ fontSize: 13 }}>Enter any public URL above to scan it for exposed data.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>URL</th>
                  <th>Score</th>
                  <th>Risk</th>
                  <th>Findings</th>
                  <th>Scanned</th>
                  <th style={{ width: 40 }}></th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id} style={{ cursor: 'pointer' }} onClick={() => setUrl(h.url)}>
                    <td style={{ maxWidth: 300 }}>
                      <a href={h.url} target="_blank" rel="noreferrer"
                        onClick={e => e.stopPropagation()}
                        style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 5, fontSize: 12 }}>
                        <Globe size={11} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 260 }}>
                          {h.url}
                        </span>
                        <ExternalLink size={10} />
                      </a>
                    </td>
                    <td style={{ fontWeight: 700, color: riskColor(h.risk_level) }}>{Math.round(h.score)}</td>
                    <td>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 700,
                        background: riskBg(h.risk_level), color: riskColor(h.risk_level),
                        border: `1px solid ${riskColor(h.risk_level)}33`
                      }}>
                        {h.risk_level}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{h.finding_count}</td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                      {new Date(h.upload_date).toLocaleString()}
                    </td>
                    <td onClick={e => e.stopPropagation()} style={{ textAlign: 'center', padding: '0 8px' }}>
                      <button
                        onClick={e => handleDelete(e, h.id)}
                        disabled={deletingId === h.id}
                        title="Delete this entry"
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer',
                          color: 'var(--text-muted)', padding: '4px 6px',
                          borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          transition: 'color 0.15s, background 0.15s',
                          opacity: deletingId === h.id ? 0.5 : 1,
                        }}
                        onMouseEnter={e => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.background = 'rgba(239,68,68,0.1)'; }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'none'; }}
                      >
                        {deletingId === h.id
                          ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2, borderColor: 'rgba(239,68,68,0.3)', borderTopColor: '#ef4444' }} />
                          : <X size={14} />}
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
