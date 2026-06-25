import React, { useState, useEffect, useCallback } from 'react';
import {
  Zap, Shield, AlertTriangle, ChevronDown, ChevronUp,
  RefreshCw, Play, Database, Target, Mail, Phone,
  Key, Lock, MapPin, CreditCard, User, Globe,
  CheckCircle, Eye, EyeOff, ArrowRight, Layers
} from 'lucide-react';
import {
  simulateFromScan, simulateAggregate, getAttackScans
} from '../api';

// ── Helpers ───────────────────────────────────────────────────────────────────
const SEVERITY_COLOR = { CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e', SAFE:'#6b7280' };
const SEVERITY_BG    = { CRITICAL:'rgba(220,38,38,0.08)', HIGH:'rgba(239,68,68,0.07)', MEDIUM:'rgba(245,158,11,0.08)', LOW:'rgba(34,197,94,0.08)', SAFE:'rgba(107,114,128,0.06)' };

const ICON_MAP = {
  mail: Mail, phone: Phone, key: Key, shield: Shield,
  'map-pin': MapPin, target: Target, lock: Lock,
  database: Database, 'credit-card': CreditCard,
};

const sColor = s => SEVERITY_COLOR[s] || '#6b7280';
const sBg    = s => SEVERITY_BG[s]    || 'transparent';

function ScoreRing({ score, risk, size = 100 }) {
  const r = size * 0.37, stroke = size * 0.055, circ = 2 * Math.PI * r;
  const filled = circ * (score / 100);
  return (
    <svg width={size} height={size} style={{ display:'block' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={sColor(risk)} strokeWidth={stroke}
        strokeDasharray={`${filled} ${circ}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition:'stroke-dasharray 1s ease' }}/>
      <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="middle"
        fill={sColor(risk)} fontSize={size*0.18} fontWeight="bold">{Math.round(score)}</text>
    </svg>
  );
}

// ── Attack Card ───────────────────────────────────────────────────────────────
function AttackCard({ attack, index }) {
  const [expanded, setExpanded] = useState(false);
  const [showDemo, setShowDemo] = useState(false);
  const IconComp = ICON_MAP[attack.icon] || Zap;
  const demoKey  = Object.keys(attack.demo || {})[0];
  const demoVal  = demoKey ? attack.demo[demoKey] : null;

  return (
    <div style={{
      borderRadius:'12px', border:`1px solid ${sColor(attack.severity)}33`,
      background:'var(--card-bg)', marginBottom:'14px', overflow:'hidden',
      transition:'box-shadow .2s',
    }}>
      {/* Header */}
      <div
        onClick={() => setExpanded(v => !v)}
        style={{ padding:'16px 20px', cursor:'pointer', display:'flex',
          alignItems:'center', gap:'14px',
          background: expanded ? sBg(attack.severity) : 'transparent',
          borderBottom: expanded ? `1px solid ${sColor(attack.severity)}22` : 'none',
        }}>
        {/* Icon */}
        <div style={{ width:'40px', height:'40px', borderRadius:'10px', flexShrink:0,
          background: sBg(attack.severity), border:`1px solid ${sColor(attack.severity)}44`,
          display:'flex', alignItems:'center', justifyContent:'center' }}>
          <IconComp size={18} color={sColor(attack.severity)}/>
        </div>

        {/* Title + badges */}
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:'8px', flexWrap:'wrap', marginBottom:'3px' }}>
            <span style={{ fontWeight:700, fontSize:'14px' }}>{attack.name}</span>
            <span style={{ fontSize:'10px', padding:'2px 7px', borderRadius:'20px', fontWeight:700,
              background: sBg(attack.severity), color: sColor(attack.severity),
              border:`1px solid ${sColor(attack.severity)}44` }}>
              {attack.severity}
            </span>
            <span style={{ fontSize:'10px', padding:'2px 7px', borderRadius:'20px', fontWeight:600,
              background:'rgba(107,114,128,0.1)', color:'var(--text-secondary)' }}>
              Confidence: {attack.confidence}
            </span>
          </div>
          <div style={{ fontSize:'12px', color:'var(--text-secondary)', lineHeight:'1.4' }}>
            {attack.description}
          </div>
        </div>

        {/* Expand icon */}
        <div style={{ flexShrink:0, color:'var(--text-secondary)' }}>
          {expanded ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div style={{ padding:'18px 20px' }}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'18px' }}>

            {/* Attack Steps */}
            <div>
              <div style={{ fontSize:'11px', fontWeight:700, textTransform:'uppercase',
                letterSpacing:'0.06em', color:'var(--text-secondary)', marginBottom:'12px',
                display:'flex', alignItems:'center', gap:'6px' }}>
                <ArrowRight size={12} color={sColor(attack.severity)}/> Attack Chain
              </div>
              {attack.steps.map((step, i) => (
                <div key={i} style={{ display:'flex', gap:'10px', marginBottom:'10px', alignItems:'flex-start' }}>
                  <div style={{ width:'22px', height:'22px', borderRadius:'50%', flexShrink:0,
                    background: sBg(attack.severity), border:`1px solid ${sColor(attack.severity)}44`,
                    display:'flex', alignItems:'center', justifyContent:'center',
                    fontSize:'10px', fontWeight:700, color: sColor(attack.severity) }}>
                    {i + 1}
                  </div>
                  <div style={{ fontSize:'12px', color:'var(--text-primary)', lineHeight:'1.5', paddingTop:'2px' }}>
                    {step}
                  </div>
                </div>
              ))}
            </div>

            {/* Mitigations */}
            <div>
              <div style={{ fontSize:'11px', fontWeight:700, textTransform:'uppercase',
                letterSpacing:'0.06em', color:'var(--text-secondary)', marginBottom:'12px',
                display:'flex', alignItems:'center', gap:'6px' }}>
                <Shield size={12} color='#22c55e'/> How to Protect Yourself
              </div>
              {attack.mitigations.map((m, i) => (
                <div key={i} style={{ display:'flex', gap:'8px', marginBottom:'8px', alignItems:'flex-start' }}>
                  <CheckCircle size={13} color='#22c55e' style={{ flexShrink:0, marginTop:'2px' }}/>
                  <div style={{ fontSize:'12px', color:'var(--text-primary)', lineHeight:'1.5' }}>{m}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Demo preview */}
          {demoVal && (
            <div style={{ marginTop:'16px', borderTop:'1px solid var(--border)', paddingTop:'14px' }}>
              <button onClick={() => setShowDemo(v => !v)}
                style={{ display:'flex', alignItems:'center', gap:'6px', background:'none', border:'none',
                  cursor:'pointer', color: sColor(attack.severity), fontWeight:700, fontSize:'12px',
                  padding:0, marginBottom: showDemo ? '10px' : 0 }}>
                {showDemo ? <EyeOff size={13}/> : <Eye size={13}/>}
                {showDemo ? 'Hide' : 'Show'} Attack Preview (How it would look)
              </button>
              {showDemo && (
                <pre style={{
                  background:'#0d0d14', color:'#e2e8f0', borderRadius:'8px',
                  padding:'14px', fontSize:'11.5px', lineHeight:'1.7',
                  fontFamily:'monospace', whiteSpace:'pre-wrap', wordBreak:'break-word',
                  border:`1px solid ${sColor(attack.severity)}33`, margin:0,
                }}>{demoVal}</pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function AttackSimulationPage() {
  const [scans,         setScans]       = useState([]);
  const [selectedScan,  setSelectedScan]= useState('aggregate');
  const [result,        setResult]      = useState(null);
  const [loading,       setLoading]     = useState(false);
  const [error,         setError]       = useState('');
  const [loadingScans,  setLoadingScans]= useState(true);

  // Load user's scan list
  const loadScans = useCallback(async () => {
    setLoadingScans(true);
    try {
      const data = await getAttackScans();
      setScans(data);
    } catch { /* ignore */ }
    finally { setLoadingScans(false); }
  }, []);

  useEffect(() => { loadScans(); }, [loadScans]);

  // Don't auto-run — page starts clean every visit

  const runSimulation = async (target) => {
    setLoading(true); setError(''); setResult(null);
    try {
      let data;
      if (target === 'aggregate') {
        data = await simulateAggregate();
      } else {
        data = await simulateFromScan(parseInt(target));
      }
      setResult(data);
    } catch(e) {
      console.error('Simulation error:', e);
      setError(e?.response?.data?.detail || 'Simulation failed. Make sure you have existing scans.');
    } finally { setLoading(false); }
  };

  const handleRun = () => runSimulation(selectedScan);

  const piiEntries = result ? Object.entries(result.pii_map || {}) : [];

  return (
    <div style={{ padding:'28px', maxWidth:'960px', margin:'0 auto',
      fontFamily:'"Inter","Segoe UI",sans-serif', color:'var(--text-primary)' }}>

      {/* ── Header ── */}
      <div style={{ marginBottom:'28px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'12px', marginBottom:'6px' }}>
          <div style={{ width:'40px', height:'40px', borderRadius:'10px',
            background:'rgba(220,38,38,0.1)', border:'1px solid rgba(220,38,38,0.3)',
            display:'flex', alignItems:'center', justifyContent:'center' }}>
            <Zap size={20} color='#dc2626'/>
          </div>
          <h1 style={{ margin:0, fontSize:'22px', fontWeight:700 }}>Attack Simulation</h1>
        </div>
        <p style={{ margin:0, fontSize:'13px', color:'var(--text-secondary)', lineHeight:'1.5' }}>
          Simulates real-world cyberattacks using the PII found across all your scans.
          See exactly how an attacker could exploit your exposed data — and how to stop them.
        </p>
      </div>

      {/* ── Scan Selector + Run ── */}
      <div style={{ display:'flex', gap:'12px', marginBottom:'24px', alignItems:'flex-end', flexWrap:'wrap' }}>
        <div style={{ flex:1, minWidth:'220px' }}>
          <label style={{ display:'block', fontSize:'11px', fontWeight:700, color:'var(--text-secondary)',
            textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:'6px' }}>
            Data Source
          </label>
          <select value={selectedScan} onChange={e => setSelectedScan(e.target.value)}
            style={{ width:'100%', padding:'10px 12px', borderRadius:'9px',
              border:'1px solid var(--border)', background:'var(--card-bg)',
              color:'var(--text-primary)', fontSize:'13px', cursor:'pointer' }}>
            <option value="aggregate">All My Scans Combined (Worst Case)</option>
            {scans.map(s => (
              <option key={s.scan_id} value={s.scan_id}>
                #{s.scan_id} — {s.filename} ({s.source}) | Score: {Math.round(s.score)} | {s.finding_count} findings
              </option>
            ))}
          </select>
        </div>
        <button onClick={handleRun} disabled={loading}
          style={{ padding:'10px 22px', borderRadius:'9px', border:'none', cursor:'pointer',
            background: loading ? 'rgba(220,38,38,0.4)' : '#dc2626',
            color:'#fff', fontWeight:700, fontSize:'13px',
            display:'flex', alignItems:'center', gap:'7px', minWidth:'150px',
            justifyContent:'center', transition:'background .2s' }}>
          {loading
            ? <><div style={{ width:'14px', height:'14px', border:'2px solid #fff',
                borderTopColor:'transparent', borderRadius:'50%', animation:'spin 1s linear infinite' }}/> Running…</>
            : <><Play size={14}/> Run Simulation</>}
        </button>
        <button onClick={() => { loadScans(); if (selectedScan) runSimulation(selectedScan); }}
          disabled={loadingScans || loading}
          style={{ padding:'10px 14px', borderRadius:'9px', border:'1px solid var(--border)',
            background:'none', color:'var(--text-secondary)', cursor:'pointer',
            display:'flex', alignItems:'center', gap:'6px', fontSize:'12px' }}>
          <RefreshCw size={13} style={{ animation: (loadingScans || loading) ? 'spin 1s linear infinite' : 'none' }}/> Refresh
        </button>
        {result && (
          <button onClick={() => { setResult(null); setError(''); setSelectedScan('aggregate'); }}
            style={{ padding:'10px 14px', borderRadius:'9px', border:'1px solid rgba(220,38,38,0.3)',
              background:'rgba(220,38,38,0.06)', color:'#dc2626', cursor:'pointer',
              display:'flex', alignItems:'center', gap:'6px', fontSize:'12px', fontWeight:600 }}>
            <AlertTriangle size={13}/> Clear Results
          </button>
        )}
      </div>
      <style>{`@keyframes spin { to { transform:rotate(360deg); } }`}</style>

      {/* ── Error ── */}
      {error && (
        <div style={{ padding:'12px 16px', borderRadius:'10px', marginBottom:'20px',
          background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.25)',
          color:'#ef4444', display:'flex', alignItems:'center', gap:'8px', fontSize:'13px' }}>
          <AlertTriangle size={15}/> {error}
        </div>
      )}

      {/* ── Results ── */}
      {result && (
        <>
          {/* Summary row */}
          <div style={{ display:'grid', gridTemplateColumns:'auto 1fr', gap:'20px',
            padding:'20px 24px', borderRadius:'14px', border:`1px solid ${sColor(result.highest_severity)}33`,
            background: sBg(result.highest_severity), marginBottom:'24px', alignItems:'center' }}>

            <ScoreRing score={result.overall_threat_score} risk={result.highest_severity} size={90}/>

            <div>
              <div style={{ display:'flex', alignItems:'center', gap:'10px', marginBottom:'6px', flexWrap:'wrap' }}>
                <span style={{ fontSize:'18px', fontWeight:800, color: sColor(result.highest_severity) }}>
                  {result.total_attacks} Attack{result.total_attacks !== 1 ? 's' : ''} Identified
                </span>
                <span style={{ fontSize:'12px', padding:'3px 10px', borderRadius:'20px', fontWeight:700,
                  background: sBg(result.highest_severity), color: sColor(result.highest_severity),
                  border:`1px solid ${sColor(result.highest_severity)}44` }}>
                  {result.highest_severity}
                </span>
              </div>
              <div style={{ fontSize:'13px', color:'var(--text-secondary)', marginBottom:'10px' }}>
                Threat Score: <strong style={{ color: sColor(result.highest_severity) }}>
                  {result.overall_threat_score}/100
                </strong>
                &nbsp;·&nbsp; Base Scan Score: {result.base_score}
                {result.total_scans && <>&nbsp;·&nbsp; Across {result.total_scans} scans, {result.total_findings} findings</>}
              </div>

              {/* PII types found */}
              {piiEntries.length > 0 && (
                <div style={{ display:'flex', flexWrap:'wrap', gap:'6px' }}>
                  <span style={{ fontSize:'11px', color:'var(--text-secondary)', alignSelf:'center' }}>Detected PII:</span>
                  {piiEntries.map(([type, vals]) => (
                    <span key={type} style={{ fontSize:'11px', padding:'2px 8px', borderRadius:'20px',
                      background:'rgba(107,114,128,0.12)', color:'var(--text-secondary)',
                      border:'1px solid var(--border)', fontWeight:600 }}>
                      {type} ({vals.length})
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* No attacks */}
          {result.total_attacks === 0 && (
            <div style={{ padding:'40px', textAlign:'center', borderRadius:'14px',
              border:'1px solid var(--border)', background:'var(--card-bg)', marginBottom:'24px' }}>
              <CheckCircle size={40} color='#22c55e' style={{ marginBottom:'12px' }}/>
              <div style={{ fontSize:'16px', fontWeight:700, marginBottom:'6px' }}>No Attack Scenarios Applicable</div>
              <div style={{ fontSize:'13px', color:'var(--text-secondary)' }}>
                No sensitive PII was found in the selected scan(s). Your data exposure is minimal.<br/>
                Try scanning files with personal information to see potential attack vectors.
              </div>
            </div>
          )}

          {/* Attack cards */}
          {result.applicable_attacks?.length > 0 && (
            <div>
              <div style={{ fontSize:'13px', fontWeight:700, color:'var(--text-secondary)',
                textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:'14px',
                display:'flex', alignItems:'center', gap:'8px' }}>
                <Layers size={14}/> Applicable Attack Scenarios — Sorted by Severity
              </div>
              {result.applicable_attacks.map((attack, i) => (
                <AttackCard key={attack.id} attack={attack} index={i}/>
              ))}
            </div>
          )}

          {/* PII breakdown */}
          {piiEntries.length > 0 && (
            <div style={{ marginTop:'24px', borderRadius:'14px', border:'1px solid var(--border)',
              background:'var(--card-bg)', overflow:'hidden' }}>
              <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)',
                fontWeight:700, fontSize:'14px', display:'flex', alignItems:'center', gap:'8px' }}>
                <Database size={15} color='#f59e0b'/> Exposed PII Used in Simulation
              </div>
              <div style={{ padding:'16px 20px', display:'flex', flexWrap:'wrap', gap:'10px' }}>
                {piiEntries.map(([type, vals]) => (
                  <div key={type} style={{ padding:'10px 14px', borderRadius:'9px',
                    background:'var(--bg)', border:'1px solid var(--border)', minWidth:'140px' }}>
                    <div style={{ fontSize:'10px', fontWeight:700, textTransform:'uppercase',
                      letterSpacing:'0.05em', color:'var(--text-secondary)', marginBottom:'4px' }}>
                      {type.replace(/_/g,' ')}
                    </div>
                    {vals.map((v, i) => (
                      <div key={i} style={{ fontSize:'12px', color:'var(--text-primary)',
                        fontFamily:'monospace', wordBreak:'break-all' }}>
                        {String(v).length > 40 ? String(v).slice(0,40)+'…' : v}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Connected workflow notice */}
          <div style={{ marginTop:'20px', padding:'14px 18px', borderRadius:'10px',
            background:'rgba(6,182,212,0.06)', border:'1px solid rgba(6,182,212,0.2)',
            display:'flex', gap:'10px', alignItems:'flex-start' }}>
            <Globe size={15} color='#06b6d4' style={{ flexShrink:0, marginTop:'1px' }}/>
            <div style={{ fontSize:'12px', color:'var(--text-secondary)', lineHeight:'1.6' }}>
              <strong style={{ color:'var(--text-primary)' }}>Connected Workflow:</strong> This simulation uses PII
              detected across <strong>Upload & Scan</strong>, <strong>URL Scanner</strong>,&nbsp;
              <strong>Social Scanner</strong>, <strong>Metadata Scanner</strong>, and&nbsp;
              <strong>Screen Monitor</strong>. The more scans you run, the more accurate the threat picture.
              Use <strong>Recommendations</strong> to fix each vulnerability.
            </div>
          </div>
        </>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <div style={{ padding:'48px', textAlign:'center', borderRadius:'14px',
          border:'2px dashed var(--border)', color:'var(--text-secondary)' }}>
          <Zap size={40} color='#dc2626' style={{ marginBottom:'12px', opacity:0.6 }}/>
          <div style={{ fontSize:'16px', fontWeight:600, marginBottom:'6px' }}>
            Ready to Simulate
          </div>
          <div style={{ fontSize:'13px' }}>
            Select a data source above and click <strong>Run Simulation</strong>
          </div>
        </div>
      )}
    </div>
  );
}
