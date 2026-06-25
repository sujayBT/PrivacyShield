import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, Search, Globe, Clock, Trash2, ChevronDown, ChevronUp,
  AlertTriangle, Shield, Activity, ExternalLink, RefreshCw,
  AtSign, Briefcase, MessageSquare, Camera, Eye
} from 'lucide-react';
import { socialScan, getSocialHistory, getSocialDetail, deleteSocialScan, clearAllSocialHistory, purgeLegacySocialScans } from '../api';

// ── Helpers ───────────────────────────────────────────────────────────────────
const riskColor = r => ({ CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e', SAFE:'#6b7280' }[r] || '#6b7280');
const riskBg    = r => ({ CRITICAL:'rgba(220,38,38,0.1)', HIGH:'rgba(239,68,68,0.12)', MEDIUM:'rgba(245,158,11,0.1)', LOW:'rgba(34,197,94,0.1)', SAFE:'rgba(107,114,128,0.08)' }[r] || 'transparent');

const PLATFORM_META = {
  twitter:   { icon: AtSign,        color: '#1d9bf0', label: 'Twitter / X',  bg: 'rgba(29,155,240,0.08)'  },
  linkedin:  { icon: Briefcase,     color: '#0a66c2', label: 'LinkedIn',     bg: 'rgba(10,102,194,0.08)'  },
  reddit:    { icon: MessageSquare, color: '#ff4500', label: 'Reddit',       bg: 'rgba(255,69,0,0.08)'    },
  instagram: { icon: Camera,        color: '#e1306c', label: 'Instagram',    bg: 'rgba(225,48,108,0.08)'  },
  github:    { icon: Eye,           color: '#333333', label: 'GitHub',       bg: 'rgba(51,51,51,0.08)'    },
  unknown:   { icon: Globe,         color: '#6b7280', label: 'Unknown',      bg: 'rgba(107,114,128,0.08)' },
};

const getPlatform = source => {
  if (!source) return 'unknown';
  if (source.includes('twitter')) return 'twitter';
  if (source.includes('linkedin')) return 'linkedin';
  if (source.includes('reddit')) return 'reddit';
  if (source.includes('instagram')) return 'instagram';
  if (source.includes('github')) return 'github';
  return 'unknown';
};

const TYPE_ICON = {
  aadhaar:'🪪', pan:'🪪', credit_card:'💳', email:'📧', phone:'📱',
  password:'🔑', otp:'🔒', face_detected:'👤', id_card_visible:'🪪', dob:'📅',
  username:'🏷️', display_name:'🧑', location:'📍', bio:'📝', website:'🔗',
  company:'🏢', twitter:'🐦',
  PERSON:'🧑', GPE:'📍', LOC:'📍', ORG:'🏢', MONEY:'💰', DATE:'📅', CARDINAL:'🔢',
  social_classification: '🛡️',
};

const SAMPLE_URLS = [
  // GitHub — free public API, 100% reliable, returns real PII fields
  { label: '⚫ GitHub: torvalds',   url: 'https://github.com/torvalds'   },
  { label: '⚫ GitHub: gvanrossum', url: 'https://github.com/gvanrossum' },
  { label: '⚫ GitHub: dhh',        url: 'https://github.com/dhh'        },
  // Twitter / X — Twitterbot UA, confirmed working
  { label: '🔵 Twitter: @NASA',     url: 'https://x.com/NASA'            },
  { label: '🔵 Twitter: @OpenAI',   url: 'https://x.com/OpenAI'          },
  // Reddit — JSON API, confirmed working
  { label: '🟠 Reddit: GallowBoob', url: 'https://www.reddit.com/user/GallowBoob/' },
  // LinkedIn — company pages work
  { label: '🔷 LinkedIn: Google',   url: 'https://www.linkedin.com/company/google/' },
];

// ── Score Ring ────────────────────────────────────────────────────────────────
function ScoreRing({ score, risk }) {
  const r = 36, stroke = 5;
  const circ = 2 * Math.PI * r;
  const filled = circ * (score / 100);
  return (
    <svg width="90" height="90" style={{ display:'block', margin:'0 auto' }}>
      <circle cx="45" cy="45" r={r} fill="none" stroke="var(--border)" strokeWidth={stroke}/>
      <circle cx="45" cy="45" r={r} fill="none"
        stroke={riskColor(risk)} strokeWidth={stroke}
        strokeDasharray={`${filled} ${circ - filled}`}
        strokeLinecap="round"
        transform="rotate(-90 45 45)"
        style={{ transition: 'stroke-dasharray 0.8s ease' }}
      />
      <text x="45" y="45" textAnchor="middle" dominantBaseline="middle"
        style={{ fontSize:16, fontWeight:800, fill: riskColor(risk) }}>
        {score}
      </text>
      <text x="45" y="58" textAnchor="middle"
        style={{ fontSize:8, fill:'var(--text-muted)', fontWeight:600 }}>
        /100
      </text>
    </svg>
  );
}

// ── Platform Badge ────────────────────────────────────────────────────────────
function PlatformBadge({ source }) {
  const key = getPlatform(source);
  const meta = PLATFORM_META[key];
  const Icon = meta.icon;
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:5,
      padding:'3px 10px', borderRadius:12, fontSize:11, fontWeight:700,
      background: meta.bg, color: meta.color, border:`1px solid ${meta.color}30`
    }}>
      <Icon size={11}/> {meta.label}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function SocialScanPage() {
  const [url,         setUrl]         = useState('');
  const [loading,     setLoading]     = useState(false);
  const [result,      setResult]      = useState(null);
  const [error,       setError]       = useState('');
  const [history,     setHistory]     = useState([]);
  const [expandedId,  setExpandedId]  = useState(null);
  const [detail,      setDetail]      = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showRecs,    setShowRecs]    = useState(false);

  const loadHistory = useCallback(async () => {
    try { setHistory(await getSocialHistory()); } catch {}
  }, []);

  useEffect(() => {
    // Auto-purge legacy false-positive entries (score=100 from old broken scanner)
    // This runs silently on every page mount — safe to call repeatedly
    purgeLegacySocialScans().catch(() => {});
    loadHistory();
  }, [loadHistory]);

  // ── Scan ──────────────────────────────────────────────────────────────────
  const handleScan = async () => {
    if (!url.trim()) return;
    setLoading(true); setError(''); setResult(null); setShowRecs(false);
    try {
      const res = await socialScan(url.trim());
      setResult(res);
      loadHistory();
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Scan failed');
    } finally {
      setLoading(false);
    }
  };

  // ── Expand history detail ─────────────────────────────────────────────────
  const loadDetail = async (id) => {
    if (expandedId === id) { setExpandedId(null); setDetail(null); return; }
    setExpandedId(id); setDetailLoading(true);
    try { setDetail(await getSocialDetail(id)); } catch {}
    setDetailLoading(false);
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    try { await deleteSocialScan(id); loadHistory(); } catch {}
    if (expandedId === id) { setExpandedId(null); setDetail(null); }
  };

  const handleKey = e => { if (e.key === 'Enter') handleScan(); };
  const handleClear = () => { setResult(null); setUrl(''); setError(''); setShowRecs(false); };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div>
      <style>{`
        @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes spin    { to{transform:rotate(360deg)} }
        .social-result { animation: fadeIn 0.4s ease; }
        .spin { animation: spin 1s linear infinite; }
      `}</style>

      {/* ── Header ── */}
      <div className="card" style={{ padding:'22px 24px', marginBottom:20 }}>
        <div className="section-title" style={{ marginBottom:6 }}>
          <Users size={16} color="var(--accent)"/> Social Media Scanner
        </div>
        <p style={{ color:'var(--text-secondary)', fontSize:13, marginBottom:20 }}>
          Scan any public social media profile (Twitter/X, LinkedIn, Reddit, Instagram) for exposed PII.
          Runs full Regex + AI NER + Vision pipeline on public profile text and avatar image.
        </p>

        {/* URL Input */}
        <div style={{ display:'flex', gap:10, marginBottom:14 }}>
          <input
            value={url} onChange={e => setUrl(e.target.value)} onKeyDown={handleKey}
            placeholder="Paste public profile URL — e.g. https://reddit.com/user/username"
            style={{
              flex:1, padding:'10px 14px', borderRadius:8, fontSize:13,
              border:'1.5px solid var(--border)', background:'var(--bg-base)',
              color:'var(--text-primary)', outline:'none',
            }}
          />
          {(result || url.trim()) && (
            <button
              onClick={handleClear}
              title="Clear"
              style={{
                padding:'10px 14px', borderRadius:8, fontSize:13, fontWeight:700,
                border:'1px solid rgba(248,113,113,0.35)',
                background:'rgba(248,113,113,0.08)',
                color:'#f87171', cursor:'pointer',
                display:'flex', alignItems:'center', gap:5,
              }}
            >
              ✕ Clear
            </button>
          )}
          <button className="btn btn-primary" style={{ minWidth:130, gap:7 }}
            onClick={handleScan} disabled={loading || !url.trim()}>
            {loading
              ? <><RefreshCw size={14} className="spin"/> Scanning…</>
              : <><Search size={14}/> Scan Profile</>
            }
          </button>
        </div>

        {/* Sample URLs */}
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'center' }}>
          <span style={{ fontSize:11, color:'var(--text-muted)' }}>Try:</span>
          {SAMPLE_URLS.map(s => (
            <button key={s.url} className="btn btn-secondary btn-sm"
              onClick={() => setUrl(s.url)} style={{ fontSize:11 }}>
              {s.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginTop:14 }}>
            <AlertTriangle size={14}/> {error}
          </div>
        )}
      </div>

      {/* ── Supported Platforms Info ── */}
      {!result && !loading && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14, marginBottom:20 }}>
          {Object.entries(PLATFORM_META).filter(([k]) => k !== 'unknown').map(([key, meta]) => {
            const Icon = meta.icon;
            return (
              <div key={key} className="card" style={{ padding:'16px 18px', textAlign:'center' }}>
                <Icon size={24} color={meta.color} style={{ marginBottom:8 }}/>
                <div style={{ fontWeight:700, fontSize:13, color: meta.color }}>{meta.label}</div>
                <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:4 }}>
                  {key === 'twitter'   && 'Via Nitter mirror'}
                  {key === 'linkedin'  && 'Public profiles only'}
                  {key === 'reddit'    && 'Via public JSON API'}
                  {key === 'instagram' && 'Limited public data'}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Scan Result ── */}
      {result && (
        <div className="social-result card" style={{ padding:0, overflow:'hidden', marginBottom:20 }}>
          {/* Result header */}
          <div style={{
            padding:'16px 22px', borderBottom:'1px solid var(--border)',
            background: riskBg(result.risk_level),
            display:'flex', gap:20, alignItems:'center', flexWrap:'wrap'
          }}>
            <ScoreRing score={result.score} risk={result.risk_level}/>
            <div style={{ flex:1, minWidth:200 }}>
              <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap', marginBottom:8 }}>
                <PlatformBadge source={`social_${result.platform}`}/>
                <span style={{
                  padding:'3px 10px', borderRadius:12, fontSize:11, fontWeight:800,
                  background: riskBg(result.risk_level), color: riskColor(result.risk_level),
                  border:`1.5px solid ${riskColor(result.risk_level)}40`
                }}>{result.risk_level}</span>
                {result.vision?.face_count > 0 && (
                  <span style={{ fontSize:11, padding:'3px 9px', borderRadius:10, background:'rgba(239,68,68,0.1)', color:'#ef4444', border:'1px solid rgba(239,68,68,0.3)' }}>
                    👤 {result.vision.face_count} face(s) in avatar
                  </span>
                )}
              </div>
              <div style={{ fontWeight:700, fontSize:16, marginBottom:4 }}>
                {result.title || result.username || result.url}
              </div>
              <div style={{ fontSize:12, color:'var(--text-muted)', marginBottom:8 }}>
                <a href={result.url} target="_blank" rel="noreferrer"
                  style={{ color:'var(--accent)', display:'inline-flex', alignItems:'center', gap:4 }}
                  onClick={e => e.stopPropagation()}>
                  <ExternalLink size={11}/> {result.url}
                </a>
              </div>
              <div style={{ display:'flex', gap:16, fontSize:12, color:'var(--text-secondary)' }}>
                <span>📋 <strong style={{ color:'var(--text-primary)' }}>{result.finding_count}</strong> findings</span>
                <span>🔍 Scan ID <strong style={{ color:'var(--text-primary)' }}>#{result.scan_id}</strong></span>
                {result.avatar_url && <span>🖼️ Avatar analysed</span>}
              </div>
            </div>
          </div>

          {/* Text preview */}
          {result.text_preview && (
            <div style={{ padding:'12px 22px', borderBottom:'1px solid var(--border)', background:'var(--bg-base)' }}>
              <div style={{ fontSize:11, fontWeight:600, color:'var(--text-muted)', marginBottom:6, textTransform:'uppercase' }}>
                Scraped Text Preview
              </div>
              <pre style={{ fontSize:11, color:'var(--text-secondary)', whiteSpace:'pre-wrap', margin:0, maxHeight:100, overflow:'auto' }}>
                {result.text_preview}
              </pre>
            </div>
          )}

          {/* Findings */}
          {result.findings?.length > 0 && (
            <div style={{ padding:'14px 22px', borderBottom:'1px solid var(--border)' }}>
              <div style={{ fontSize:11, fontWeight:600, color:'var(--text-muted)', marginBottom:10, textTransform:'uppercase' }}>
                Detected PII ({result.finding_count})
              </div>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                {[...new Set(result.findings.map(f => f.type))].map(type => {
                  const count = result.findings.filter(f => f.type === type).length;
                  return (
                    <span key={type} style={{
                      display:'inline-flex', alignItems:'center', gap:5,
                      padding:'4px 10px', borderRadius:10, fontSize:11, fontWeight:600,
                      background:'var(--accent-light)', color:'var(--accent)',
                      border:'1px solid rgba(32,101,209,0.2)'
                    }}>
                      {TYPE_ICON[type] || '⚠️'} {type}
                      {count > 1 && <span style={{ background:'var(--accent)', color:'#fff', borderRadius:8, padding:'0 5px', fontSize:9 }}>{count}</span>}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recommendations toggle */}
          {result.recommendations?.length > 0 && (
            <div>
              <button style={{
                width:'100%', padding:'11px 22px', background:'none', border:'none',
                borderBottom: showRecs ? '1px solid var(--border)' : 'none',
                cursor:'pointer', display:'flex', alignItems:'center', gap:8,
                color:'var(--accent)', fontSize:12, fontWeight:700, textAlign:'left'
              }} onClick={() => setShowRecs(v => !v)}>
                <Shield size={13}/> {result.recommendations.length} Security Recommendations
                {showRecs ? <ChevronUp size={13}/> : <ChevronDown size={13}/>}
              </button>
              {showRecs && (
                <div style={{ padding:'14px 22px' }}>
                  {result.recommendations.slice(0, 5).map((rec, i) => (
                    <div key={i} style={{
                      padding:'10px 14px', borderRadius:8, marginBottom:8,
                      background:'var(--bg-base)', border:'1px solid var(--border)'
                    }}>
                      <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:4 }}>
                        <span style={{
                          fontSize:10, fontWeight:800, padding:'1px 7px', borderRadius:8,
                          background: rec.severity === 'CRITICAL' ? 'rgba(220,38,38,0.12)' : 'rgba(245,158,11,0.1)',
                          color: rec.severity === 'CRITICAL' ? '#dc2626' : '#f59e0b'
                        }}>{rec.severity}</span>
                        <span style={{ fontSize:12, fontWeight:700 }}>{rec.category}</span>
                      </div>
                      <div style={{ fontSize:11, color:'var(--text-secondary)' }}>
                        {(rec.advice || [])[0]}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Scan History ── */}
      <div className="card" style={{ padding:0, overflow:'hidden' }}>
        <div style={{ padding:'14px 22px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <Clock size={15} style={{ color:'var(--accent)' }}/>
            <span className="section-title" style={{ margin:0 }}>Scan History ({history.length})</span>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            {history.length > 0 && (
              <button
                className="btn btn-sm"
                style={{
                  border:'1px solid rgba(248,113,113,0.35)',
                  background:'rgba(248,113,113,0.07)',
                  color:'#f87171', fontSize:11, fontWeight:700,
                  display:'flex', alignItems:'center', gap:5,
                }}
                onClick={async () => {
                  if (!window.confirm('Clear ALL social scan history?')) return;
                  await clearAllSocialHistory();
                  setHistory([]);
                  setExpandedId(null);
                  setDetail(null);
                }}
              >
                ✕ Clear All
              </button>
            )}
            <button className="btn btn-secondary btn-sm" onClick={loadHistory}>
              <RefreshCw size={12}/> Refresh
            </button>
          </div>
        </div>

        {history.length === 0 ? (
          <div style={{ padding:48, textAlign:'center', color:'var(--text-secondary)' }}>
            <Users size={36} style={{ opacity:0.2, display:'block', margin:'0 auto 12px' }}/>
            <p style={{ fontWeight:600, marginBottom:6 }}>No social scans yet</p>
            <p style={{ fontSize:13 }}>Paste a public profile URL above and click "Scan Profile".</p>
          </div>
        ) : (
          history.map(s => {
            const isExpanded = expandedId === s.scan_id;
            return (
              <div key={s.scan_id}>
                <div style={{
                  padding:'12px 22px', borderBottom:'1px solid var(--border)',
                  display:'flex', alignItems:'center', gap:12, cursor:'pointer'
                }} onClick={() => loadDetail(s.scan_id)}>
                  <PlatformBadge source={s.source}/>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontWeight:600, fontSize:13, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {s.filename?.replace(/\.txt$/, '') || s.source_url}
                    </div>
                    <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:2, display:'flex', gap:10 }}>
                      <span>🔗 {(s.source_url || '').slice(0, 50)}{(s.source_url || '').length > 50 ? '…' : ''}</span>
                    </div>
                  </div>
                  <div style={{ textAlign:'center', minWidth:65 }}>
                    <div style={{ fontSize:18, fontWeight:800, color: riskColor(s.risk_level) }}>{s.score}</div>
                    <div style={{ fontSize:10, color:'var(--text-muted)' }}>score</div>
                  </div>
                  <span style={{
                    padding:'3px 9px', borderRadius:10, fontSize:11, fontWeight:700,
                    background: riskBg(s.risk_level), color: riskColor(s.risk_level),
                    border:`1px solid ${riskColor(s.risk_level)}30`, minWidth:70, textAlign:'center'
                  }}>{s.risk_level}</span>
                  <button className="btn btn-danger btn-sm"
                    onClick={e => handleDelete(s.scan_id, e)}>
                    <Trash2 size={12}/>
                  </button>
                  {isExpanded ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div style={{ padding:'16px 22px', background:'var(--bg-base)', borderBottom:'1px solid var(--border)' }}>
                    {detailLoading ? (
                      <div style={{ textAlign:'center', padding:'20px 0', color:'var(--text-muted)' }}>
                        <RefreshCw size={18} className="spin"/> Loading…
                      </div>
                    ) : detail ? (
                      <>
                        {/* Findings table */}
                        {detail.findings?.length > 0 ? (
                          <div className="table-container" style={{ marginBottom:12 }}>
                            <table>
                              <thead><tr><th>Type</th><th>Value</th><th>Source</th><th>Confidence</th></tr></thead>
                              <tbody>
                                {detail.findings.slice(0, 15).map((f, i) => (
                                  <tr key={i}>
                                    <td>
                                      <span style={{ fontSize:11, background:'var(--accent-light)', color:'var(--accent)', borderRadius:5, padding:'2px 7px' }}>
                                        {TYPE_ICON[f.type]||'⚠️'} {f.type}
                                      </span>
                                    </td>
                                    <td style={{ fontSize:11, maxWidth:220, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{f.value}</td>
                                    <td style={{ fontSize:11 }}>
                                      <span style={{ padding:'1px 6px', borderRadius:6, fontSize:10, fontWeight:600,
                                        background: f.source === 'ai' ? 'rgba(139,92,246,0.1)' : 'var(--bg-base)',
                                        color: f.source === 'ai' ? '#8b5cf6' : 'var(--text-muted)' }}>
                                        {f.source || 'regex'}
                                      </span>
                                    </td>
                                    <td style={{ fontSize:11, color:'var(--text-muted)' }}>
                                      {f.confidence ? `${(f.confidence * 100).toFixed(0)}%` : '—'}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div style={{ textAlign:'center', padding:'12px 0', color:'var(--success)', fontSize:13, fontWeight:600 }}>
                            ✅ No PII found in this scan
                          </div>
                        )}

                        {/* Text preview */}
                        {detail.extracted_text_preview && (
                          <div style={{ marginTop:8 }}>
                            <div style={{ fontSize:10, color:'var(--text-muted)', fontWeight:600, marginBottom:4, textTransform:'uppercase' }}>Text Preview</div>
                            <pre style={{ fontSize:10, color:'var(--text-secondary)', whiteSpace:'pre-wrap', margin:0, maxHeight:80, overflow:'auto',
                              background:'var(--bg-surface)', padding:'8px 12px', borderRadius:6, border:'1px solid var(--border)' }}>
                              {detail.extracted_text_preview}
                            </pre>
                          </div>
                        )}

                        {/* Recommendations button */}
                        {detail.recommendations?.length > 0 && (
                          <div style={{ marginTop:12, display:'flex', gap:8 }}>
                            <button className="btn btn-secondary btn-sm"
                              onClick={() => window.location.href=`/recommendations?id=${detail.scan_id}`}>
                              <Shield size={12}/> View {detail.recommendations.length} Recommendations
                            </button>
                            <a href={detail.source_url} target="_blank" rel="noreferrer">
                              <button className="btn btn-secondary btn-sm">
                                <ExternalLink size={12}/> Open Profile
                              </button>
                            </a>
                          </div>
                        )}
                      </>
                    ) : null}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
