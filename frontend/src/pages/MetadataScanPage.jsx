import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search, Upload, FileText, Image, File, Table2,
  Clock, ChevronDown, ChevronUp, AlertTriangle,
  Shield, MapPin, User, Calendar, Camera, Cpu,
  Download, RefreshCw, ExternalLink, CheckCircle, Eye
} from 'lucide-react';
import { metadataScan, getMetadataHistory, getMetadataForScan, metadataPdfReport, metadataClean } from '../api';

// ── Helpers ────────────────────────────────────────────────────────────────
const riskColor = r => ({ CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e', SAFE:'#22c55e' }[r] || '#6b7280');
const riskBg    = r => ({ CRITICAL:'rgba(220,38,38,0.08)', HIGH:'rgba(239,68,68,0.08)', MEDIUM:'rgba(245,158,11,0.08)', LOW:'rgba(34,197,94,0.08)', SAFE:'rgba(34,197,94,0.06)' }[r] || 'transparent');
const sanitize  = (v) => String(v || '').replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '').trim();

const FILE_ICON = { image: Image, pdf: FileText, word: FileText, excel: Table2, powerpoint: FileText, unknown: File };

const FIELD_ICONS = {
  gps_latitude: MapPin, gps_longitude: MapPin, gps_full: MapPin,
  author: User, last_modified_by: User, artist: User, creator: User,
  creation_date: Calendar, modification_date: Calendar, date_time_original: Calendar,
  camera_make: Camera, camera_model: Camera, software: Cpu,
};

// ── Score Ring ─────────────────────────────────────────────────────────────
function ScoreRing({ score, risk }) {
  const r = 36, stroke = 5, circ = 2 * Math.PI * r;
  const filled = circ * (score / 100);
  return (
    <svg width="90" height="90" style={{ display:'block', margin:'0 auto' }}>
      <circle cx="45" cy="45" r={r} fill="none" stroke="var(--border)" strokeWidth={stroke}/>
      <circle cx="45" cy="45" r={r} fill="none" stroke={riskColor(risk)} strokeWidth={stroke}
        strokeDasharray={`${filled} ${circ}`} strokeLinecap="round"
        transform="rotate(-90 45 45)" style={{ transition:'stroke-dasharray .8s ease' }}/>
      <text x="45" y="47" textAnchor="middle" dominantBaseline="middle"
        fill={riskColor(risk)} fontSize="16" fontWeight="bold">{Math.round(score)}</text>
    </svg>
  );
}

// ── Sensitive Field Row ────────────────────────────────────────────────────
function FieldRow({ field, value, risk, reason, label }) {
  const IconComp = FIELD_ICONS[field] || Shield;
  const displayLabel = label || field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const displayVal = sanitize(value);
  if (!displayVal) return null;
  return (
    <div style={{ display:'flex', alignItems:'flex-start', gap:'10px', padding:'12px 0',
      borderBottom:'1px solid var(--border)' }}>
      <div style={{ width:'32px', height:'32px', borderRadius:'8px', display:'flex',
        alignItems:'center', justifyContent:'center', flexShrink:0,
        background: riskBg(risk), border:`1px solid ${riskColor(risk)}22`, marginTop:'2px' }}>
        <IconComp size={16} color={riskColor(risk)}/>
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'2px' }}>
          <div style={{ fontSize:'11px', color:'var(--text-secondary)', fontWeight:700,
            textTransform:'uppercase', letterSpacing:'0.05em' }}>{displayLabel}</div>
          <span style={{ fontSize:'9px', padding:'1px 6px', borderRadius:'4px', fontWeight:800,
            background: riskBg(risk), color: riskColor(risk), border:`1px solid ${riskColor(risk)}33` }}>{risk}</span>
        </div>
        <div style={{ fontSize:'14px', color:'var(--text-primary)', fontWeight:600,
          wordBreak:'break-all', marginBottom:'4px' }}>{displayVal}</div>
        {reason && (
          <div style={{ fontSize:'12px', color: riskColor(risk), opacity:0.85, fontWeight:500, fontStyle:'italic' }}>
            <span style={{ marginRight:'4px' }}>⚠</span>{reason}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────
export default function MetadataScanPage() {
  const [dragging,    setDragging]    = useState(false);
  const [scanning,    setScanning]    = useState(false);
  const [result,      setResult]      = useState(null);
  const [error,       setError]       = useState('');
  const [history,     setHistory]     = useState([]);
  const [loadingHist, setLoadingHist] = useState(false);
  const [expanded,    setExpanded]    = useState({});
  const [showRecs,    setShowRecs]    = useState(false);
  const [downloading, setDownloading] = useState(false);
  const fileRef  = useRef(null);
  const cleanRef = useRef(null);

  const loadHistory = useCallback(async () => {
    setLoadingHist(true);
    try { setHistory(await getMetadataHistory()); }
    catch { /* ignore */ }
    finally { setLoadingHist(false); }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Scan file for privacy risks
  const handleFile = async (file) => {
    if (!file) return;
    setScanning(true); setError(''); setResult(null); setShowRecs(false);
    try {
      const raw = await metadataScan(file);
      setResult(raw);
      loadHistory();
    } catch(e) {
      setError(e?.response?.data?.detail || e?.message || 'Scan failed. Please try again.');
    } finally { setScanning(false); }
  };

  // Clean file (strip metadata) and download
  const handleClean = async (file) => {
    if (!file) return;
    setScanning(true); setError('');
    try {
      const blob = await metadataClean(file);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `CLEANED_${file.name}`;
      a.click(); URL.revokeObjectURL(url);
    } catch { setError('Metadata cleaning failed. Try a different file format.'); }
    finally { setScanning(false); }
  };

  // Download PDF report for current result
  const handleDownloadPDF = async () => {
    if (!result?.scan_id) return;
    setDownloading(true);
    try {
      const blob = await metadataPdfReport(result.scan_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `metadata_report_${result.filename}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch { setError('PDF generation failed.'); }
    finally { setDownloading(false); }
  };

  // Load a history item's full metadata
  const loadHistoryScan = async (scan_id) => {
    setScanning(true); setError(''); setResult(null);
    try { setResult(await getMetadataForScan(scan_id)); loadHistory(); }
    catch(e) { setError(e?.response?.data?.detail || 'Failed to load scan.'); }
    finally { setScanning(false); }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  return (
    <div style={{ padding:'28px', maxWidth:'900px', margin:'0 auto',
      fontFamily:'"Inter", "Segoe UI", sans-serif', color:'var(--text-primary)' }}>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* ── Header ── */}
      <div style={{ marginBottom:'28px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'12px', marginBottom:'6px' }}>
          <div style={{ width:'40px', height:'40px', borderRadius:'10px', background:'rgba(6,182,212,0.12)',
            border:'1px solid rgba(6,182,212,0.3)', display:'flex', alignItems:'center', justifyContent:'center' }}>
            <Search size={20} color="#06b6d4"/>
          </div>
          <h1 style={{ margin:0, fontSize:'22px', fontWeight:700 }}>Metadata Scanner</h1>
        </div>
        <p style={{ margin:0, fontSize:'13px', color:'var(--text-secondary)', lineHeight:'1.5' }}>
          Audit and strip hidden metadata from images, PDFs, Word, Excel, and PowerPoint files.
          Detect identity leaks: author names, local file paths, GPS coordinates, and device info.
        </p>
      </div>

      {/* ── Drop Zone ── */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{
          border: `2px dashed ${dragging ? '#06b6d4' : 'var(--border)'}`,
          borderRadius:'14px', padding:'36px 20px', textAlign:'center',
          background: dragging ? 'rgba(6,182,212,0.05)' : 'var(--card-bg)',
          transition:'all .2s', marginBottom:'24px',
          boxShadow: dragging ? '0 0 0 4px rgba(6,182,212,0.15)' : 'none',
        }}>

        {/* Hidden file inputs */}
        <input ref={fileRef} type="file"
          accept=".jpg,.jpeg,.png,.tiff,.webp,.bmp,.pdf,.docx,.xlsx,.doc,.xls,.pptx,.ppt"
          style={{ display:'none' }} onChange={e => { handleFile(e.target.files[0]); e.target.value=''; }}/>
        <input ref={cleanRef} type="file"
          accept=".jpg,.jpeg,.png,.pdf,.docx,.xlsx,.pptx"
          style={{ display:'none' }} onChange={e => { handleClean(e.target.files[0]); e.target.value=''; }}/>

        <div style={{ fontSize:'13px', color:'var(--text-secondary)', marginBottom:'16px' }}>
          Drop a file here or use the buttons below
        </div>

        <div style={{ display:'flex', justifyContent:'center', gap:'12px', marginBottom:'14px', flexWrap:'wrap' }}>
          <button onClick={(e) => { e.stopPropagation(); fileRef.current?.click(); }}
            style={{ padding:'11px 22px', borderRadius:'10px', background:'#06b6d4', color:'white',
              border:'none', fontWeight:700, cursor:'pointer', fontSize:'13px',
              display:'flex', alignItems:'center', gap:'8px' }}>
            <Upload size={16}/> Scan for Privacy Risks
          </button>
          <button onClick={(e) => { e.stopPropagation(); cleanRef.current?.click(); }}
            style={{ padding:'11px 22px', borderRadius:'10px', background:'rgba(35,134,54,0.08)', color:'#238636',
              border:'1px solid rgba(35,134,54,0.4)', fontWeight:700, cursor:'pointer', fontSize:'13px',
              display:'flex', alignItems:'center', gap:'8px' }}>
            <RefreshCw size={16}/> Clean & Download
          </button>
        </div>

        <div style={{ fontSize:'11px', color:'var(--text-secondary)' }}>
          JPG · PNG · PDF · DOCX · XLSX · PPTX &nbsp;|&nbsp; Max 25 MB
        </div>

        {scanning && (
          <div style={{ marginTop:'14px', display:'flex', alignItems:'center', gap:'8px',
            justifyContent:'center', color:'#06b6d4', fontSize:'13px' }}>
            <div style={{ width:'14px', height:'14px', border:'2px solid #06b6d4',
              borderTopColor:'transparent', borderRadius:'50%', animation:'spin 1s linear infinite' }}/>
            Processing file...
          </div>
        )}
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{ padding:'12px 16px', borderRadius:'10px', marginBottom:'20px',
          background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.25)',
          color:'#ef4444', display:'flex', alignItems:'center', gap:'8px', fontSize:'13px' }}>
          <AlertTriangle size={15}/> {error}
        </div>
      )}

      {/* ── Result Card ── */}
      {result && (
        <div style={{ borderRadius:'14px', border:'1px solid var(--border)',
          background:'var(--card-bg)', marginBottom:'28px', overflow:'hidden' }}>

          {/* Score Header */}
          <div style={{ padding:'20px 24px', display:'flex', alignItems:'center',
            gap:'16px', borderBottom:'1px solid var(--border)', background: riskBg(result.risk_level) }}>
            <ScoreRing score={result.score} risk={result.risk_level}/>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'6px', flexWrap:'wrap' }}>
                <span style={{ fontSize:'11px', padding:'3px 9px', borderRadius:'20px', fontWeight:700,
                  background: riskBg(result.risk_level), color: riskColor(result.risk_level),
                  border:`1px solid ${riskColor(result.risk_level)}44` }}>
                  {(result.file_type || 'FILE').toUpperCase()}
                </span>
                <span style={{ fontSize:'11px', padding:'3px 9px', borderRadius:'20px', fontWeight:700,
                  background: riskBg(result.risk_level), color: riskColor(result.risk_level),
                  border:`1px solid ${riskColor(result.risk_level)}44` }}>
                  {result.risk_level} RISK
                </span>
                {result.has_gps && (
                  <span style={{ fontSize:'11px', padding:'3px 9px', borderRadius:'20px', fontWeight:700,
                    background:'rgba(220,38,38,0.1)', color:'#dc2626', border:'1px solid rgba(220,38,38,0.3)' }}>
                    📍 GPS FOUND
                  </span>
                )}
              </div>
              <div style={{ fontSize:'15px', fontWeight:700, marginBottom:'3px',
                overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {result.filename}
              </div>
              <div style={{ fontSize:'12px', color:'var(--text-secondary)' }}>
                {(result.sensitive_findings || []).length} sensitive findings
                &nbsp;·&nbsp; {result.file_size_kb} KB
                &nbsp;·&nbsp; Scan #{result.scan_id}
              </div>
            </div>
            <button onClick={handleDownloadPDF} disabled={downloading}
              style={{ padding:'8px 14px', borderRadius:'8px', border:'none', cursor:'pointer',
                background:'rgba(6,182,212,0.12)', color:'#06b6d4', fontWeight:600, fontSize:'12px',
                display:'flex', alignItems:'center', gap:'6px', flexShrink:0 }}>
              <Download size={13}/> {downloading ? 'Generating…' : 'PDF Report'}
            </button>
          </div>

          {/* GPS Alert */}
          {result.has_gps && result.gps_maps_link && (
            <div style={{ padding:'12px 24px', background:'rgba(220,38,38,0.06)',
              borderBottom:'1px solid rgba(220,38,38,0.2)', display:'flex', alignItems:'center', gap:'10px' }}>
              <MapPin size={15} color="#dc2626"/>
              <span style={{ fontSize:'13px', color:'#dc2626', fontWeight:600 }}>
                🚨 GPS Physical Location Leaked — this image embeds your real-world location!
              </span>
              <a href={result.gps_maps_link} target="_blank" rel="noopener noreferrer"
                style={{ marginLeft:'auto', fontSize:'12px', color:'#06b6d4',
                  display:'flex', alignItems:'center', gap:'4px', textDecoration:'none' }}>
                View on Google Maps <ExternalLink size={11}/>
              </a>
            </div>
          )}

          {/* ── Category A: Sensitive Findings ── */}
          <div style={{ padding:'20px 24px' }}>
            <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'14px' }}>
              <div style={{ width:'8px', height:'8px', borderRadius:'50%', background:'#ef4444' }}/>
              <h3 style={{ margin:0, fontSize:'12px', fontWeight:800,
                textTransform:'uppercase', letterSpacing:'0.1em', color:'#ef4444' }}>
                Category A — Sensitive Privacy Findings
              </h3>
            </div>
            {!result.sensitive_findings || result.sensitive_findings.length === 0 ? (
              <div style={{ padding:'14px 16px', borderRadius:'8px', background:'rgba(34,197,94,0.05)',
                color:'#22c55e', fontSize:'13px', fontWeight:600, border:'1px solid rgba(34,197,94,0.2)',
                display:'flex', alignItems:'center', gap:'8px' }}>
                <CheckCircle size={15}/> No sensitive personal information detected in metadata.
              </div>
            ) : (
              result.sensitive_findings.map((f, i) => (
                <FieldRow key={i} field={f.field} value={f.value} risk={f.risk}
                  reason={f.reason} label={f.label}/>
              ))
            )}
          </div>

          {/* ── Category B: Informational Fields ── */}
          {result.informational_fields?.length > 0 && (
            <div style={{ padding:'20px 24px', borderTop:'1px solid var(--border)',
              background:'rgba(248,250,252,0.4)' }}>
              <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'14px' }}>
                <div style={{ width:'8px', height:'8px', borderRadius:'50%', background:'#6b7280' }}/>
                <h3 style={{ margin:0, fontSize:'12px', fontWeight:800,
                  textTransform:'uppercase', letterSpacing:'0.1em', color:'var(--text-secondary)' }}>
                  Category B — Informational Data (No Privacy Risk)
                </h3>
              </div>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(190px, 1fr))', gap:'10px' }}>
                {result.informational_fields.map((f, i) => (
                  <div key={i} style={{ padding:'10px 12px', borderRadius:'8px',
                    background:'var(--card-bg)', border:'1px solid var(--border)' }}>
                    <div style={{ fontSize:'10px', color:'var(--text-secondary)',
                      textTransform:'uppercase', fontWeight:700, marginBottom:'3px' }}>{f.label}</div>
                    <div style={{ fontSize:'13px', fontWeight:600, color:'var(--text-primary)',
                      wordBreak:'break-all' }}>{sanitize(f.value)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Recommendations ── */}
          {result.recommendations?.length > 0 && (
            <div style={{ borderTop:'1px solid var(--border)' }}>
              <button onClick={() => setShowRecs(v => !v)}
                style={{ width:'100%', padding:'14px 24px', background:'none', border:'none',
                  cursor:'pointer', display:'flex', alignItems:'center', gap:'8px',
                  color:'var(--text-secondary)', fontSize:'13px', fontWeight:600 }}>
                <Shield size={14} color="#f59e0b"/>
                Security Recommendations ({result.recommendations.length})
                {showRecs ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
              </button>
              {showRecs && (
                <div style={{ padding:'0 24px 20px' }}>
                  {result.recommendations.map((rec, i) => (
                    <div key={i} style={{ marginBottom:'10px', padding:'12px 14px', borderRadius:'8px',
                      background:'var(--card-bg)', border:`1px solid ${riskColor(rec.severity)}33` }}>
                      <div style={{ fontWeight:700, fontSize:'13px', marginBottom:'6px',
                        color: riskColor(rec.severity) }}>
                        [{rec.severity}] {rec.title}
                      </div>
                      {rec.advice?.map((a, j) => (
                        <div key={j} style={{ fontSize:'12px', color:'var(--text-secondary)',
                          marginBottom:'3px', paddingLeft:'10px' }}>• {a}</div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Scan History ── */}
      <div style={{ borderRadius:'14px', border:'1px solid var(--border)', background:'var(--card-bg)' }}>
        <div style={{ padding:'16px 20px', borderBottom:'1px solid var(--border)',
          display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div style={{ display:'flex', alignItems:'center', gap:'8px', fontWeight:700, fontSize:'15px' }}>
            <Clock size={16} color="#06b6d4"/>
            Metadata Scan History ({history.length})
          </div>
          <button onClick={loadHistory} disabled={loadingHist}
            style={{ padding:'6px 12px', borderRadius:'7px', border:'1px solid var(--border)',
              background:'none', cursor:'pointer', color:'var(--text-secondary)',
              display:'flex', alignItems:'center', gap:'5px', fontSize:'12px' }}>
            <RefreshCw size={12}/> Refresh
          </button>
        </div>

        {history.length === 0 ? (
          <div style={{ padding:'32px', textAlign:'center', color:'var(--text-secondary)', fontSize:'13px' }}>
            No metadata scans yet. Upload a file above to start.
          </div>
        ) : (
          history.map(item => {
            const IconC = FILE_ICON[item.file_type] || File;
            const isExp = expanded[item.scan_id];
            return (
              <div key={item.scan_id} style={{ borderBottom:'1px solid var(--border)' }}>
                <div style={{ padding:'14px 20px', display:'flex', alignItems:'center', gap:'12px', cursor:'pointer' }}
                  onClick={() => setExpanded(p => ({ ...p, [item.scan_id]: !p[item.scan_id] }))}>
                  <div style={{ width:'32px', height:'32px', borderRadius:'8px',
                    background: riskBg(item.risk_level), border:`1px solid ${riskColor(item.risk_level)}33`,
                    display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <IconC size={14} color={riskColor(item.risk_level)}/>
                  </div>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontWeight:600, fontSize:'13px', overflow:'hidden',
                      textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{item.filename}</div>
                    <div style={{ fontSize:'11px', color:'var(--text-secondary)' }}>
                      {item.created_at?.slice(0, 16)}
                    </div>
                  </div>
                  <span style={{ fontWeight:800, fontSize:'18px', color: riskColor(item.risk_level),
                    width:'40px', textAlign:'center' }}>{Math.round(item.score)}</span>
                  <span style={{ fontSize:'11px', padding:'3px 8px', borderRadius:'20px', fontWeight:700,
                    background: riskBg(item.risk_level), color: riskColor(item.risk_level),
                    border:`1px solid ${riskColor(item.risk_level)}44`, minWidth:'60px', textAlign:'center' }}>
                    {item.risk_level}
                  </span>
                  {isExp ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
                </div>
                {isExp && (
                  <div style={{ padding:'0 20px 14px', borderTop:'1px solid var(--border)' }}>
                    <button onClick={() => loadHistoryScan(item.scan_id)}
                      style={{ marginTop:'10px', padding:'7px 14px', borderRadius:'7px', border:'none',
                        cursor:'pointer', background:'rgba(6,182,212,0.1)', color:'#06b6d4',
                        fontWeight:600, fontSize:'12px', display:'flex', alignItems:'center', gap:'5px' }}>
                      <Eye size={12}/> View Full Metadata
                    </button>
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
