import React, { useState, useCallback, useEffect } from 'react';
import { cloudScanLink, cloudBatchUpload, getCloudHistory, getCloudScanDetail } from '../api';
import {
  Cloud, Link2, UploadCloud, Clock, X, AlertCircle, Globe, CheckCircle,
  ExternalLink, ChevronDown, ChevronUp, Shield, Layers
} from 'lucide-react';
import AIBadge from '../components/AIBadge';
import VisionBadge from '../components/VisionBadge';

const riskColor = (r) => ({ CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e' }[r] || '#22c55e');
const riskBg   = (r) => ({ CRITICAL:'rgba(220,38,38,0.1)', HIGH:'rgba(239,68,68,0.1)', MEDIUM:'rgba(245,158,11,0.1)', LOW:'rgba(34,197,94,0.1)' }[r] || 'rgba(34,197,94,0.1)');
const STORAGE_KEY = 'cloudScanResult';

const SOURCE_ICONS  = { gdrive:'🟢', dropbox:'🔵', onedrive:'🔷', direct_url:'🌐', batch_upload:'📦' };
const SOURCE_LABELS = { gdrive:'Google Drive', dropbox:'Dropbox', onedrive:'OneDrive', direct_url:'Direct URL', batch_upload:'Batch Upload' };

// Confirmed working PDF links — tested live (200 application/pdf)
const SAMPLE_CLOUD_LINKS = [
  {
    label: '📄 Sample PDF (20 KB)',
    url:   'https://www.orimi.com/pdf-test.pdf',
    note:  'orimi.com — confirmed 200 OK, application/pdf'
  },
  {
    label: '📄 PDF Object sample',
    url:   'https://pdfobject.com/pdf/sample.pdf',
    note:  'pdfobject.com — confirmed 200 OK, application/pdf'
  },
  {
    label: '📋 Plain text file',
    url:   'https://filesamples.com/samples/document/txt/sample1.txt',
    note:  'filesamples.com — confirmed 200 OK, text/plain'
  },
];

const ScoreRing = ({ score, risk }) => {
  const color = riskColor(risk);
  const r = 40; const circ = 2 * Math.PI * r;
  const offset = circ - (Math.min(score,100)/100)*circ;
  return (
    <div style={{ position:'relative', display:'inline-flex', alignItems:'center', justifyContent:'center', width:96, height:96 }}>
      <svg width="96" height="96" style={{ transform:'rotate(-90deg)' }}>
        <circle cx="48" cy="48" r={r} fill="none" stroke="var(--border)" strokeWidth="7"/>
        <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="7"
          strokeDasharray={circ} strokeDashoffset={offset}
          style={{ transition:'stroke-dashoffset 1s ease', strokeLinecap:'round' }}/>
      </svg>
      <div style={{ position:'absolute', textAlign:'center' }}>
        <div style={{ fontSize:20, fontWeight:800, lineHeight:1, color }}>{Math.round(score)}</div>
        <div style={{ fontSize:10, color:'var(--text-secondary)' }}>/100</div>
      </div>
    </div>
  );
};

export default function CloudScanPage() {
  const [tab, setTab] = useState('link');  // 'link' | 'batch'
  const [linkUrl, setLinkUrl] = useState('');
  const [batchFiles, setBatchFiles] = useState([]);
  const [drag, setDrag] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [batchResults, setBatchResults] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null);

  // Persist last result
  const [result, setResultState] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null; } catch { return null; }
  });
  const setResult = (r) => { setResultState(r); r ? localStorage.setItem(STORAGE_KEY, JSON.stringify(r)) : localStorage.removeItem(STORAGE_KEY); };

  const loadHistory = useCallback(async () => {
    try { setHistory(await getCloudHistory()); } catch {} finally { setLoadingHistory(false); }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const handleScanLink = async () => {
    if (!linkUrl.trim()) return;
    setScanning(true); setError(''); setResult(null); setBatchResults(null);
    try {
      const data = await cloudScanLink(linkUrl.trim());
      setResult(data);
      loadHistory();
    } catch(e) {
      setError(e.response?.data?.detail || e.message || 'Scan failed');
    } finally { setScanning(false); }
  };

  const handleBatchScan = async () => {
    if (!batchFiles.length) return;
    setScanning(true); setError(''); setResult(null); setBatchResults(null);
    try {
      const data = await cloudBatchUpload(batchFiles);
      setBatchResults(data);
      loadHistory();
    } catch(e) {
      setError(e.response?.data?.detail || e.message || 'Batch scan failed');
    } finally { setScanning(false); }
  };

  const handleClear = () => { setResult(null); setBatchResults(null); setError(''); setLinkUrl(''); setBatchFiles([]); };

  const handleDrop = useCallback((e) => {
    e.preventDefault(); setDrag(false);
    const dropped = Array.from(e.dataTransfer.files);
    setBatchFiles(prev => [...prev, ...dropped].slice(0, 10));
  }, []);

  const loadDetail = async (id) => {
    if (expandedId === id) { setExpandedId(null); setDetail(null); return; }
    setExpandedId(id);
    try { setDetail(await getCloudScanDetail(id)); } catch { setDetail(null); }
  };

  return (
    <div>
      {/* Header */}
      <div className="card" style={{ padding:'20px 24px', marginBottom:20 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
          <div className="section-title" style={{ margin:0 }}>
            <Cloud size={16} color="var(--accent)"/> Cloud Scanner
          </div>
          {(result || batchResults) && (
            <button className="btn btn-danger btn-sm" onClick={handleClear}><X size={13}/> Clear</button>
          )}
        </div>
        <p style={{ color:'var(--text-secondary)', fontSize:13, marginBottom:16 }}>
          Scan files from public cloud links (Google Drive, Dropbox, OneDrive) or upload multiple files at once.
        </p>

        {/* Tabs */}
        <div style={{ display:'flex', gap:8, marginBottom:16 }}>
          {[['link','🔗 Cloud Link'], ['batch','📦 Batch Upload']].map(([k,l]) => (
            <button key={k} onClick={() => setTab(k)} className={`btn btn-sm ${tab===k ? 'btn-primary' : 'btn-secondary'}`}>{l}</button>
          ))}
        </div>

        {/* Link tab */}
        {tab === 'link' && (<>
          <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
            <div style={{ position:'relative', flex:'1 1 340px' }}>
              <Link2 size={14} style={{ position:'absolute', left:12, top:'50%', transform:'translateY(-50%)', color:'var(--text-muted)', pointerEvents:'none' }}/>
              <input className="input" style={{ paddingLeft:36, width:'100%' }}
                placeholder="https://drive.google.com/file/d/... or Dropbox / OneDrive link"
                value={linkUrl} onChange={e => setLinkUrl(e.target.value)}
                onKeyDown={e => e.key==='Enter' && handleScanLink()} disabled={scanning}/>
            </div>
            <button className="btn btn-primary" style={{ minWidth:140 }} onClick={handleScanLink} disabled={scanning || !linkUrl.trim()}>
              {scanning ? <><div className="spinner" style={{ borderColor:'rgba(255,255,255,0.3)', borderTopColor:'white' }}/> Scanning…</> : <><Cloud size={14}/> Scan Link</>}
            </button>
          </div>

          {/* Sample cloud links */}
          {!result && !scanning && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 7 }}>
                Try:
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {SAMPLE_CLOUD_LINKS.map((s, i) => (
                  <button key={i} onClick={() => setLinkUrl(s.url)}
                    title={s.note}
                    style={{
                      background: 'var(--bg-base)', border: '1px solid var(--border)',
                      borderRadius: 20, padding: '3px 10px', fontSize: 11, cursor: 'pointer',
                      color: 'var(--text-secondary)', fontWeight: 500, whiteSpace: 'nowrap',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>
                Paste a Google Drive, Dropbox, or OneDrive share link above.
              </div>
            </div>
          )}
        </>)}

        {/* Batch tab */}
        {tab === 'batch' && (
          <div>
            <div className={`dropzone${drag?' active':''}`}
              onDrop={handleDrop} onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={()=>setDrag(false)}
              onClick={() => document.getElementById('cloud-file-input').click()}
              style={{ minHeight:100 }}>
              <div className="dropzone-icon"><UploadCloud size={26} style={{ color:'var(--accent)' }}/></div>
              <div style={{ fontWeight:700, color:'var(--text-primary)', marginBottom:4 }}>Drag & drop up to 10 files</div>
              <div style={{ fontSize:12, color:'var(--text-secondary)' }}>PNG, JPG, PDF supported</div>
              <input id="cloud-file-input" type="file" multiple accept=".png,.jpg,.jpeg,.pdf" style={{ display:'none' }}
                onChange={e => setBatchFiles(Array.from(e.target.files).slice(0,10))}/>
            </div>
            {batchFiles.length > 0 && (
              <div style={{ marginTop:12, display:'flex', flexWrap:'wrap', gap:6, marginBottom:12 }}>
                {batchFiles.map((f,i) => (
                  <span key={i} style={{ fontSize:11, background:'var(--accent-light)', color:'var(--accent)', border:'1px solid rgba(32,101,209,0.2)', borderRadius:6, padding:'3px 10px', display:'flex', alignItems:'center', gap:6 }}>
                    📄 {f.name}
                    <X size={10} style={{ cursor:'pointer' }} onClick={() => setBatchFiles(prev => prev.filter((_,j) => j!==i))}/>
                  </span>
                ))}
              </div>
            )}
            <button className="btn btn-primary" style={{ width:'100%' }} onClick={handleBatchScan} disabled={scanning || !batchFiles.length}>
              {scanning ? <><div className="spinner" style={{ borderColor:'rgba(255,255,255,0.3)', borderTopColor:'white' }}/> Scanning {batchFiles.length} file(s)…</> : <><Layers size={14}/> Batch Scan ({batchFiles.length})</>}
            </button>
          </div>
        )}

        {error && <div className="alert alert-error" style={{ marginTop:14, marginBottom:0 }}><AlertCircle size={14}/> {error}</div>}
      </div>

      {/* Single link result */}
      {result && (
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:20 }}>
          <div className="card" style={{ padding:24 }}>
            <div className="section-title"><Shield size={15} color="var(--accent)"/> Result</div>
            <div style={{ marginBottom:14, padding:'10px 14px', background:'var(--bg-base)', borderRadius:8, border:'1px solid var(--border)' }}>
              <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:3 }}>SOURCE</div>
              <div style={{ fontSize:12, fontWeight:700, color:'var(--accent)' }}>
                {SOURCE_ICONS[result.source]} {SOURCE_LABELS[result.source] || result.source}
              </div>
              <div style={{ fontSize:11, color:'var(--text-secondary)', marginTop:2 }}>{result.filename}</div>
              {result.size_bytes && <div style={{ fontSize:10, color:'var(--text-muted)', marginTop:2 }}>{(result.size_bytes/1024).toFixed(1)} KB</div>}
            </div>
            <div style={{ display:'flex', gap:16, alignItems:'center', marginBottom:16 }}>
              <ScoreRing score={result.score} risk={result.risk_level}/>
              <div>
                <div style={{ fontSize:11, color:'var(--text-secondary)', marginBottom:6 }}>Risk Level</div>
                <span style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'4px 12px', borderRadius:20, fontSize:12, fontWeight:800, background:riskBg(result.risk_level), color:riskColor(result.risk_level), border:`1px solid ${riskColor(result.risk_level)}44` }}>
                  {result.risk_level==='CRITICAL'?'🔴':result.risk_level==='HIGH'?'🟠':result.risk_level==='MEDIUM'?'🟡':'🟢'} {result.risk_level}
                </span>
                <div style={{ marginTop:8, fontSize:12, color:'var(--text-secondary)' }}><strong style={{ color:'var(--text-primary)' }}>{result.finding_count}</strong> findings</div>
              </div>
            </div>
            {(result.vision_doc_type || result.vision_face_count > 0) && (
              <VisionBadge docType={result.vision_doc_type} faceCount={result.vision_face_count||0} isIdDoc={result.vision_is_id_doc}/>
            )}
          </div>
          <div className="card" style={{ padding:24 }}>
            <div className="section-title">🔍 Findings ({result.findings?.length||0})</div>
            {result.findings?.length > 0 ? (
              <div style={{ maxHeight:280, overflowY:'auto' }}>
                {result.findings.map((f,i) => (
                  <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'7px 0', borderBottom:'1px solid var(--border)', fontSize:12 }}>
                    <div>
                      <span style={{ fontWeight:700, color:'var(--accent)', marginRight:8, textTransform:'uppercase', fontSize:10 }}>{f.type}</span>
                      <span style={{ color:'var(--text-primary)', fontFamily:'monospace', maxWidth:180, display:'inline-block', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{f.value}</span>
                    </div>
                    {f.ai_confidence != null && <AIBadge confidence={f.ai_confidence} small/>}
                  </div>
                ))}
              </div>
            ) : <div style={{ textAlign:'center', padding:'28px 12px' }}>
              <CheckCircle size={30} color="#22c55e" style={{ marginBottom: 8 }}/>
              <div style={{ color: '#22c55e', fontWeight: 700, fontSize: 14, marginBottom: 4 }}>All Clear — No PII Detected</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>No sensitive data found in this file.</div>
            </div>}
            <div style={{ marginTop:16, display:'flex', gap:8 }}>
              <button className="btn btn-secondary" style={{ flex:1, fontSize:12 }}
                onClick={() => window.open(`${window.location.origin}/report?id=${result.scan_id}`)}>📄 View Report</button>
              <button className="btn btn-secondary" style={{ flex:1, fontSize:12 }}
                onClick={() => window.open(`${window.location.origin}/recommendations?id=${result.scan_id}`)}>💡 Tips</button>
            </div>
          </div>
        </div>
      )}

      {/* Batch results */}
      {batchResults && (
        <div className="card" style={{ padding:0, overflow:'hidden', marginBottom:20 }}>
          <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:8 }}>
            <Layers size={15} style={{ color:'var(--accent)' }}/>
            <span className="section-title" style={{ margin:0 }}>Batch Results — {batchResults.batch_count} file(s)</span>
          </div>
          <div className="table-container">
            <table>
              <thead><tr><th>File</th><th>Score</th><th>Risk</th><th>Findings</th><th>Vision</th><th>Status</th></tr></thead>
              <tbody>
                {batchResults.results.map((r,i) => (
                  <tr key={i}>
                    <td style={{ fontWeight:600, fontSize:12, maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{r.filename}</td>
                    <td style={{ fontWeight:700, color:riskColor(r.risk_level) }}>{Math.round(r.score)}</td>
                    <td><span style={{ padding:'2px 8px', borderRadius:10, fontSize:11, fontWeight:700, background:riskBg(r.risk_level), color:riskColor(r.risk_level) }}>{r.risk_level}</span></td>
                    <td style={{ fontSize:12 }}>{r.finding_count}</td>
                    <td>{r.vision_doc_type && <span style={{ fontSize:10, color:'var(--accent)', fontWeight:600 }}>📄 {r.vision_doc_type.replace('_',' ')}</span>}</td>
                    <td>{r.error ? <span style={{ color:'var(--danger)', fontSize:11 }}>❌ {r.error.slice(0,40)}</span> : <span style={{ color:'var(--success)', fontSize:11 }}>✅ OK</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* History */}
      <div className="card" style={{ padding:0, overflow:'hidden' }}>
        <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:8 }}>
          <Clock size={15} style={{ color:'var(--accent)' }}/>
          <span className="section-title" style={{ margin:0 }}>Cloud Scan History</span>
        </div>
        {loadingHistory ? (
          <div style={{ padding:40, textAlign:'center' }}>
            <div className="spinner" style={{ margin:'0 auto', borderColor:'var(--border)', borderTopColor:'var(--accent)', width:28, height:28, borderWidth:3 }}/>
          </div>
        ) : history.length === 0 ? (
          <div style={{ padding:48, textAlign:'center', color:'var(--text-secondary)' }}>
            <Cloud size={36} style={{ marginBottom:12, opacity:0.2, display:'block', margin:'0 auto 12px' }}/>
            <p style={{ fontWeight:600, marginBottom:6 }}>No cloud scans yet</p>
            <p style={{ fontSize:13 }}>Paste a Google Drive, Dropbox or OneDrive public link above.</p>
          </div>
        ) : (
          <div>
            {history.map(h => (
              <div key={h.scan_id}>
                <div style={{ padding:'12px 20px', borderBottom:'1px solid var(--border)', cursor:'pointer', display:'flex', alignItems:'center', gap:12 }}
                  onClick={() => loadDetail(h.scan_id)}>
                  <span style={{ fontSize:18 }}>{SOURCE_ICONS[h.source] || '☁️'}</span>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontWeight:600, fontSize:13, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{h.filename}</div>
                    <div style={{ fontSize:11, color:'var(--text-muted)' }}>{SOURCE_LABELS[h.source]} · {new Date(h.upload_date).toLocaleString()}</div>
                  </div>
                  <span style={{ fontWeight:800, color:riskColor(h.risk_level), fontSize:16 }}>{Math.round(h.score)}</span>
                  <span style={{ padding:'2px 9px', borderRadius:12, fontSize:11, fontWeight:700, background:riskBg(h.risk_level), color:riskColor(h.risk_level) }}>{h.risk_level}</span>
                  <span style={{ fontSize:11, color:'var(--text-muted)' }}>{h.finding_count} findings</span>
                  {expandedId === h.scan_id ? <ChevronUp size={15}/> : <ChevronDown size={15}/>}
                </div>

                {/* Expanded detail */}
                {expandedId === h.scan_id && detail && (
                  <div style={{ padding:'16px 20px', background:'var(--bg-base)', borderBottom:'1px solid var(--border)' }}>
                    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
                      {/* Findings */}
                      <div>
                        <div style={{ fontWeight:700, fontSize:12, color:'var(--text-primary)', marginBottom:8 }}>🔍 Findings ({detail.findings?.length||0})</div>
                        {detail.findings?.slice(0,8).map((f,i) => (
                          <div key={i} style={{ fontSize:11, padding:'4px 0', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between' }}>
                            <span style={{ color:'var(--accent)', fontWeight:700, textTransform:'uppercase', marginRight:8, flexShrink:0 }}>{f.type}</span>
                            <span style={{ fontFamily:'monospace', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:180 }}>{f.value}</span>
                          </div>
                        ))}
                      </div>
                      {/* Recommendations */}
                      <div>
                        <div style={{ fontWeight:700, fontSize:12, color:'var(--text-primary)', marginBottom:8 }}>💡 Top Recommendations</div>
                        {(detail.recommendations||[]).slice(0,3).map((rec,i) => (
                          <div key={i} style={{ marginBottom:8, padding:'8px 10px', borderRadius:7, background:'var(--bg-card)', border:'1px solid var(--border)' }}>
                            <div style={{ fontSize:11, fontWeight:700, color: rec.severity==='HIGH'?'var(--danger)':rec.severity==='MEDIUM'?'var(--warning)':'var(--success)' }}>{rec.severity} — {rec.category}</div>
                            <div style={{ fontSize:11, color:'var(--text-secondary)', marginTop:3 }}>{rec.advice?.[0]}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                    {detail.vision_doc_type && (
                      <div style={{ marginTop:12 }}>
                        <VisionBadge docType={detail.vision_doc_type} faceCount={detail.vision_face_count||0} isIdDoc={detail.vision_is_id_doc}/>
                      </div>
                    )}
                    {detail.extracted_text_preview && (
                      <div style={{ marginTop:12 }}>
                        <div style={{ fontSize:11, fontWeight:700, color:'var(--text-muted)', marginBottom:4 }}>EXTRACTED TEXT PREVIEW</div>
                        <pre style={{ fontSize:10, color:'var(--text-secondary)', background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:7, padding:'8px 12px', whiteSpace:'pre-wrap', wordBreak:'break-word', maxHeight:100, overflowY:'auto' }}>{detail.extracted_text_preview}</pre>
                      </div>
                    )}
                    <div style={{ marginTop:12, display:'flex', gap:8 }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => window.location.href=`/report?id=${h.scan_id}`}>📄 Full Report</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => window.location.href=`/recommendations?id=${h.scan_id}`}>💡 Recommendations</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
