import React, { useState, useEffect, useCallback, useRef } from 'react';
import { UploadCloud, X, Trash2, RefreshCw, AlertTriangle, CheckCircle,
  ChevronDown, ChevronUp, Layers, Shield, Database, Zap } from 'lucide-react';
import { batchScanUpload, getBatchJobs, getBatchJob, deleteBatchJob, getBatchAggregate } from '../api';

const RC = { CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e', SAFE:'#6b7280' };
const RB = { CRITICAL:'rgba(220,38,38,0.08)', HIGH:'rgba(239,68,68,0.07)', MEDIUM:'rgba(245,158,11,0.08)', LOW:'rgba(34,197,94,0.08)', SAFE:'rgba(107,114,128,0.06)' };
const rc = r => RC[r] || '#6b7280';
const rb = r => RB[r] || 'transparent';

function RiskBadge({ risk }) {
  return (
    <span style={{ fontSize:'10px', padding:'2px 8px', borderRadius:'20px', fontWeight:700,
      background:rb(risk), color:rc(risk), border:`1px solid ${rc(risk)}33` }}>{risk}</span>
  );
}

function ResultRow({ r, idx }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderRadius:'8px', border:`1px solid ${rc(r.risk_level)}22`,
      background:'var(--card-bg)', marginBottom:'8px', overflow:'hidden' }}>
      <div onClick={() => setOpen(v=>!v)} style={{ padding:'10px 14px', cursor:'pointer',
        display:'flex', alignItems:'center', gap:'10px' }}>
        <span style={{ fontSize:'12px', color:'var(--text-secondary)', minWidth:'24px' }}>#{idx+1}</span>
        <span style={{ flex:1, fontSize:'12px', fontWeight:600, overflow:'hidden',
          textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{r.filename}</span>
        <RiskBadge risk={r.risk_level}/>
        <span style={{ fontSize:'12px', fontWeight:700, color:rc(r.risk_level) }}>{r.score}</span>
        <span style={{ fontSize:'11px', color:'var(--text-secondary)' }}>{r.finding_count} findings</span>
        {open ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
      </div>
      {open && r.findings?.length > 0 && (
        <div style={{ padding:'10px 14px', borderTop:`1px solid ${rc(r.risk_level)}22`,
          display:'flex', flexWrap:'wrap', gap:'6px' }}>
          {r.findings.map((f,i) => (
            <span key={i} style={{ fontSize:'11px', padding:'2px 8px', borderRadius:'20px',
              background:'rgba(107,114,128,0.1)', color:'var(--text-secondary)',
              border:'1px solid var(--border)' }}>
              {f.type}: {String(f.value).slice(0,40)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function JobCard({ job, onDelete, onExpand, expanded }) {
  return (
    <div style={{ borderRadius:'12px', border:`1px solid ${rc(job.highest_risk)}33`,
      background:'var(--card-bg)', marginBottom:'12px', overflow:'hidden' }}>
      <div onClick={onExpand} style={{ padding:'14px 18px', cursor:'pointer',
        display:'flex', alignItems:'center', gap:'12px', flexWrap:'wrap' }}>
        <div style={{ flex:1 }}>
          <div style={{ fontWeight:700, fontSize:'13px', marginBottom:'2px' }}>{job.label}</div>
          <div style={{ fontSize:'11px', color:'var(--text-secondary)' }}>{job.created_at}</div>
        </div>
        <RiskBadge risk={job.highest_risk}/>
        <span style={{ fontSize:'12px', color:'var(--text-secondary)' }}>{job.file_count} files</span>
        <span style={{ fontSize:'13px', fontWeight:700, color:rc(job.highest_risk) }}>Score {job.avg_score}</span>
        {job.alert_count > 0 && (
          <span style={{ fontSize:'10px', padding:'2px 7px', borderRadius:'20px',
            background:'rgba(220,38,38,0.1)', color:'#dc2626', border:'1px solid rgba(220,38,38,0.3)',
            fontWeight:700 }}>⚠ {job.alert_count} alerts</span>
        )}
        <button onClick={e=>{e.stopPropagation();onDelete(job.job_id);}}
          style={{ background:'none', border:'none', cursor:'pointer', color:'#ef4444', padding:'4px' }}>
          <Trash2 size={13}/>
        </button>
        {expanded ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
      </div>
      {expanded && <JobDetail jobId={job.job_id}/>}
    </div>
  );
}

function JobDetail({ jobId }) {
  const [data, setData] = useState(null);
  useEffect(() => { getBatchJob(jobId).then(setData).catch(()=>{}); }, [jobId]);
  if (!data) return <div style={{ padding:'16px', textAlign:'center', fontSize:'12px', color:'var(--text-secondary)' }}>Loading…</div>;
  return (
    <div style={{ padding:'14px 18px', borderTop:'1px solid var(--border)' }}>
      {data.errors?.length > 0 && (
        <div style={{ marginBottom:'10px', padding:'8px 12px', borderRadius:'8px',
          background:'rgba(239,68,68,0.07)', border:'1px solid rgba(239,68,68,0.2)',
          fontSize:'12px', color:'#ef4444' }}>
          {data.errors.map((e,i) => <div key={i}>⚠ {e.filename}: {e.error}</div>)}
        </div>
      )}
      {(data.results||[]).map((r,i) => <ResultRow key={i} r={r} idx={i}/>)}
    </div>
  );
}

export default function BatchScanPage() {
  const [files,      setFiles]     = useState([]);
  const [label,      setLabel]     = useState('');
  const [drag,       setDrag]      = useState(false);
  const [uploading,  setUploading] = useState(false);
  const [result,     setResult]    = useState(null);
  const [error,      setError]     = useState('');
  const [jobs,       setJobs]      = useState([]);
  const [aggregate,  setAggregate] = useState(null);
  const [expanded,   setExpanded]  = useState(null);
  const [loadingJobs,setLoadingJobs]=useState(true);
  const inputRef = useRef();

  const loadJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const [j, agg] = await Promise.all([getBatchJobs(), getBatchAggregate()]);
      setJobs(j); setAggregate(agg);
    } catch{}
    finally { setLoadingJobs(false); }
  }, []);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  const addFiles = fs => {
    const valid = Array.from(fs).filter(f => /\.(png|jpe?g|webp|bmp)$/i.test(f.name));
    setFiles(prev => {
      const names = new Set(prev.map(f=>f.name));
      const fresh = valid.filter(f => !names.has(f.name));
      return [...prev, ...fresh].slice(0, 50);
    });
  };

  const handleSubmit = async () => {
    if (!files.length) return;
    setUploading(true); setError(''); setResult(null);
    try {
      const fd = new FormData();
      files.forEach(f => fd.append('screenshots', f));
      if (label.trim()) fd.append('label', label.trim());
      const data = await batchScanUpload(fd);
      setResult(data); setFiles([]); setLabel('');
      await loadJobs();
    } catch(e) {
      setError(e?.response?.data?.detail || 'Upload failed. Make sure files are PNG/JPG/JPEG/WEBP.');
    } finally { setUploading(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this batch job?')) return;
    try { await deleteBatchJob(id); await loadJobs(); if(expanded===id) setExpanded(null); } catch{}
  };

  return (
    <div style={{ padding:'28px', maxWidth:'960px', margin:'0 auto',
      fontFamily:'"Inter","Segoe UI",sans-serif', color:'var(--text-primary)' }}>

      {/* Header */}
      <div style={{ marginBottom:'24px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'12px', marginBottom:'6px' }}>
          <div style={{ width:'40px', height:'40px', borderRadius:'10px',
            background:'rgba(168,85,247,0.1)', border:'1px solid rgba(168,85,247,0.3)',
            display:'flex', alignItems:'center', justifyContent:'center' }}>
            <Layers size={20} color='#a855f7'/>
          </div>
          <h1 style={{ margin:0, fontSize:'22px', fontWeight:700 }}>Batch Screenshot Scanner</h1>
        </div>
        <p style={{ margin:0, fontSize:'13px', color:'var(--text-secondary)', lineHeight:'1.5' }}>
          Upload up to 50 screenshots at once. Each is scanned for PII, faces, ID cards, and sensitive content — all results aggregated in one report.
        </p>
      </div>

      {/* Aggregate stats */}
      {aggregate?.total_jobs > 0 && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))',
          gap:'12px', marginBottom:'24px' }}>
          {[
            { label:'Total Jobs',   value:aggregate.total_jobs,   color:'#a855f7' },
            { label:'Total Files',  value:aggregate.total_files,  color:'#60a5fa' },
            { label:'Alerts Raised',value:aggregate.total_alerts, color:'#dc2626' },
            { label:'Batch Score',  value:aggregate.avg_score,    color:rc(aggregate.highest_risk) },
          ].map(s => (
            <div key={s.label} style={{ padding:'14px 16px', borderRadius:'10px',
              border:'1px solid var(--border)', background:'var(--card-bg)' }}>
              <div style={{ fontSize:'10px', color:'var(--text-secondary)', fontWeight:700,
                textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:'4px' }}>{s.label}</div>
              <div style={{ fontSize:'22px', fontWeight:800, color:s.color }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Upload zone */}
      <div style={{ padding:'20px', borderRadius:'14px', border:'1px solid var(--border)',
        background:'var(--card-bg)', marginBottom:'20px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'14px',
          fontWeight:700, fontSize:'14px' }}>
          <UploadCloud size={15} color='#a855f7'/> Upload Screenshots
        </div>

        {/* Label input */}
        <input value={label} onChange={e=>setLabel(e.target.value)}
          placeholder="Batch label (optional, e.g. 'Work session 22 Apr')"
          style={{ width:'100%', padding:'9px 12px', borderRadius:'9px',
            border:'1px solid var(--border)', background:'var(--bg)',
            color:'var(--text-primary)', fontSize:'13px', marginBottom:'12px',
            boxSizing:'border-box' }}/>

        {/* Drop zone */}
        <div
          className={`dropzone ${drag?'active':''}`}
          style={{ padding:'20px', minHeight:'90px', cursor:'pointer' }}
          onDrop={e=>{e.preventDefault();setDrag(false);addFiles(e.dataTransfer.files);}}
          onDragOver={e=>{e.preventDefault();setDrag(true);}}
          onDragLeave={()=>setDrag(false)}
          onClick={()=>inputRef.current.click()}>
          <UploadCloud size={24} color='#a855f7' style={{ display:'block', margin:'0 auto 8px' }}/>
          <div style={{ textAlign:'center', fontSize:'13px', color:'var(--text-secondary)' }}>
            Drop <strong>up to 50</strong> PNG / JPG / WEBP screenshots here or <strong style={{color:'#a855f7'}}>click to browse</strong>
          </div>
          <input ref={inputRef} type="file" multiple accept=".png,.jpg,.jpeg,.webp,.bmp"
            style={{ display:'none' }} onChange={e=>addFiles(e.target.files)}/>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div style={{ marginTop:'12px' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
              marginBottom:'8px', fontSize:'12px', color:'var(--text-secondary)' }}>
              <span>{files.length} file{files.length!==1?'s':''} selected</span>
              <button onClick={()=>setFiles([])} style={{ background:'none', border:'none',
                color:'#ef4444', cursor:'pointer', fontSize:'12px', display:'flex', gap:'4px', alignItems:'center' }}>
                <X size={12}/> Clear all
              </button>
            </div>
            <div style={{ maxHeight:'140px', overflowY:'auto', display:'flex', flexWrap:'wrap', gap:'6px' }}>
              {files.map((f,i) => (
                <span key={i} style={{ fontSize:'11px', padding:'3px 8px', borderRadius:'20px',
                  background:'rgba(168,85,247,0.1)', color:'#a855f7',
                  border:'1px solid rgba(168,85,247,0.3)', display:'flex', alignItems:'center', gap:'4px' }}>
                  {f.name.slice(0,28)}{f.name.length>28?'…':''}
                  <X size={10} style={{ cursor:'pointer' }}
                    onClick={()=>setFiles(prev=>prev.filter((_,j)=>j!==i))}/>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ marginTop:'12px', padding:'10px 14px', borderRadius:'8px',
            background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.25)',
            color:'#ef4444', fontSize:'12px', display:'flex', gap:'8px', alignItems:'center' }}>
            <AlertTriangle size={13}/> {error}
          </div>
        )}

        <button onClick={handleSubmit} disabled={uploading||files.length===0}
          style={{ marginTop:'14px', width:'100%', padding:'11px', borderRadius:'9px',
            border:'none', cursor: files.length===0?'not-allowed':'pointer',
            background: files.length===0?'rgba(168,85,247,0.3)':'#a855f7',
            color:'#fff', fontWeight:700, fontSize:'13px',
            display:'flex', alignItems:'center', justifyContent:'center', gap:'7px',
            transition:'background .2s' }}>
          {uploading
            ? <><div style={{ width:'14px', height:'14px', border:'2px solid #fff',
                borderTopColor:'transparent', borderRadius:'50%', animation:'spin 1s linear infinite' }}/> Scanning {files.length} files…</>
            : <><Zap size={14}/> Scan {files.length||''} Screenshot{files.length!==1?'s':''}</>}
        </button>
        <style>{`@keyframes spin{to{transform:rotate(360deg);}}`}</style>
      </div>

      {/* Latest result */}
      {result && (
        <div style={{ padding:'20px', borderRadius:'14px', marginBottom:'20px',
          border:`1px solid ${rc(result.highest_risk)}33`, background:rb(result.highest_risk) }}>
          <div style={{ display:'flex', alignItems:'center', gap:'10px', marginBottom:'12px', flexWrap:'wrap' }}>
            <CheckCircle size={18} color='#22c55e'/>
            <span style={{ fontWeight:700, fontSize:'15px' }}>Batch Complete — {result.label}</span>
            <RiskBadge risk={result.highest_risk}/>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(130px,1fr))', gap:'10px', marginBottom:'14px' }}>
            {[
              ['Processed',    result.processed],
              ['Batch Score',  result.avg_score],
              ['Max Score',    result.max_score],
              ['Alerts',       result.alert_count],
              ['Errors',       result.errors?.length||0],
            ].map(([l,v]) => (
              <div key={l} style={{ padding:'10px 14px', borderRadius:'8px',
                background:'var(--card-bg)', border:'1px solid var(--border)' }}>
                <div style={{ fontSize:'10px', color:'var(--text-secondary)', fontWeight:700,
                  textTransform:'uppercase', marginBottom:'3px' }}>{l}</div>
                <div style={{ fontSize:'18px', fontWeight:800 }}>{v}</div>
              </div>
            ))}
          </div>
          {result.errors?.length>0 && (
            <div style={{ padding:'8px 12px', borderRadius:'8px', marginBottom:'10px',
              background:'rgba(239,68,68,0.07)', border:'1px solid rgba(239,68,68,0.2)',
              fontSize:'12px', color:'#ef4444' }}>
              {result.errors.map((e,i)=><div key={i}>⚠ {e.filename}: {e.error}</div>)}
            </div>
          )}
          {result.pii_type_counts && Object.keys(result.pii_type_counts).length>0 && (
            <div style={{ display:'flex', flexWrap:'wrap', gap:'6px', marginBottom:'12px' }}>
              <span style={{ fontSize:'11px', color:'var(--text-secondary)', alignSelf:'center' }}>PII Found:</span>
              {Object.entries(result.pii_type_counts).map(([t,c])=>(
                <span key={t} style={{ fontSize:'11px', padding:'2px 8px', borderRadius:'20px',
                  background:'rgba(107,114,128,0.1)', color:'var(--text-secondary)',
                  border:'1px solid var(--border)', fontWeight:600 }}>{t} ({c})</span>
              ))}
            </div>
          )}
          {result.results?.map((r,i) => <ResultRow key={i} r={r} idx={i}/>)}
        </div>
      )}

      {/* Job history */}
      <div style={{ borderRadius:'14px', border:'1px solid var(--border)',
        background:'var(--card-bg)', overflow:'hidden' }}>
        <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)',
          display:'flex', alignItems:'center', gap:'8px', justifyContent:'space-between' }}>
          <div style={{ display:'flex', alignItems:'center', gap:'8px', fontWeight:700, fontSize:'14px' }}>
            <Database size={14} color='#a855f7'/> Past Batch Jobs
          </div>
          <button onClick={loadJobs} style={{ background:'none', border:'none', cursor:'pointer',
            color:'var(--text-secondary)', display:'flex', alignItems:'center', gap:'5px', fontSize:'12px' }}>
            <RefreshCw size={12} style={{ animation:loadingJobs?'spin 1s linear infinite':'none' }}/> Refresh
          </button>
        </div>
        <div style={{ padding:'16px 20px' }}>
          {loadingJobs && <div style={{ textAlign:'center', fontSize:'12px', color:'var(--text-secondary)' }}>Loading…</div>}
          {!loadingJobs && jobs.length===0 && (
            <div style={{ textAlign:'center', padding:'30px', color:'var(--text-secondary)', fontSize:'13px' }}>
              <Layers size={32} color='#a855f7' style={{ opacity:0.4, marginBottom:'10px', display:'block', margin:'0 auto 10px' }}/>
              No batch jobs yet. Upload screenshots above to get started.
            </div>
          )}
          {jobs.map(j => (
            <JobCard key={j.job_id} job={j}
              expanded={expanded===j.job_id}
              onExpand={()=>setExpanded(prev=>prev===j.job_id?null:j.job_id)}
              onDelete={handleDelete}/>
          ))}
        </div>
      </div>

      {/* Workflow note */}
      <div style={{ marginTop:'16px', padding:'12px 16px', borderRadius:'10px',
        background:'rgba(168,85,247,0.06)', border:'1px solid rgba(168,85,247,0.2)',
        fontSize:'12px', color:'var(--text-secondary)', lineHeight:'1.6',
        display:'flex', gap:'8px', alignItems:'flex-start' }}>
        <Shield size={13} color='#a855f7' style={{ flexShrink:0, marginTop:'1px' }}/>
        <span>
          <strong style={{color:'var(--text-primary)'}}>Connected Workflow:</strong> Every scan from this batch 
          is automatically included in <strong>Score History</strong> and <strong>Attack Simulation</strong>.
          High-risk batches will appear in <strong>Recommendations</strong> with actionable steps.
        </span>
      </div>
    </div>
  );
}
