import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { uploadScan, getScan, blurScan, getBaseUrl } from '../api';
import { UploadCloud, FileImage, X, ZoomIn, Download, Shield, Mail, Phone, Key,
  ChevronDown, ChevronUp, CreditCard, Fingerprint, Calendar, Hash, MessageSquare,
  User, MapPin, Building2, DollarSign, Users } from 'lucide-react';
import { useAuthImage } from '../hooks/useAuthImage';
import Lightbox from '../components/Lightbox';
import AIBadge from '../components/AIBadge';
import VisionBadge from '../components/VisionBadge';
const STORAGE_KEY = 'activeScan';

const riskColor = (risk) => ({
  CRITICAL: '#dc2626',
  HIGH:     '#ef4444',
  MEDIUM:   '#f59e0b',
  LOW:      '#22c55e',
}[risk] || '#22c55e');

// ─── Regex-detected finding types (9 types) ───────────────────────────────
const FINDING_TYPES = [
  { type: 'password',     label: 'Passwords',     icon: Key,           bg: 'rgba(220,38,38,0.1)',   color: '#dc2626', border: 'rgba(220,38,38,0.3)',   method: 'regex' },
  { type: 'aadhaar',     label: 'Aadhaar IDs',   icon: Fingerprint,   bg: 'rgba(239,68,68,0.1)',   color: '#ef4444', border: 'rgba(239,68,68,0.3)',   method: 'regex' },
  { type: 'pan_card',    label: 'PAN Cards',     icon: CreditCard,    bg: 'rgba(185,28,28,0.1)',   color: '#b91c1c', border: 'rgba(185,28,28,0.3)',   method: 'regex' },
  { type: 'credit_card', label: 'Credit Cards',  icon: CreditCard,    bg: 'rgba(245,158,11,0.1)',  color: '#f59e0b', border: 'rgba(245,158,11,0.3)',  method: 'regex' },
  { type: 'cvv',         label: 'CVV Codes',     icon: Hash,          bg: 'rgba(245,158,11,0.08)', color: '#d97706', border: 'rgba(245,158,11,0.25)', method: 'regex' },
  { type: 'otp',         label: 'OTPs',          icon: MessageSquare, bg: 'rgba(245,158,11,0.06)', color: '#b45309', border: 'rgba(245,158,11,0.2)',  method: 'regex' },
  { type: 'dob',         label: 'Date of Birth', icon: Calendar,      bg: 'rgba(124,58,237,0.1)',  color: '#7c3aed', border: 'rgba(124,58,237,0.3)',  method: 'regex' },
  { type: 'email',       label: 'Emails',        icon: Mail,          bg: 'rgba(32,101,209,0.1)',  color: '#2065d1', border: 'rgba(32,101,209,0.25)', method: 'regex' },
  { type: 'phone',       label: 'Phone Numbers', icon: Phone,         bg: 'rgba(34,197,94,0.1)',   color: '#22c55e', border: 'rgba(34,197,94,0.25)',  method: 'regex' },
  // ─── AI NER-detected types (spaCy) ──────────────────────────────────────
  { type: 'person_name',  label: 'Person Names',   icon: User,        bg: 'rgba(6,182,212,0.1)',   color: '#06b6d4', border: 'rgba(6,182,212,0.3)',   method: 'ai' },
  { type: 'location',     label: 'Locations',      icon: MapPin,      bg: 'rgba(20,184,166,0.1)',  color: '#14b8a6', border: 'rgba(20,184,166,0.3)',  method: 'ai' },
  { type: 'organization', label: 'Organizations',  icon: Building2,   bg: 'rgba(99,102,241,0.1)',  color: '#6366f1', border: 'rgba(99,102,241,0.3)',  method: 'ai' },
  { type: 'id_number',    label: 'ID Numbers',     icon: Hash,        bg: 'rgba(236,72,153,0.1)',  color: '#ec4899', border: 'rgba(236,72,153,0.3)',  method: 'ai' },
  { type: 'date',         label: 'Dates',          icon: Calendar,    bg: 'rgba(168,85,247,0.1)',  color: '#a855f7', border: 'rgba(168,85,247,0.3)',  method: 'ai' },
  { type: 'financial',    label: 'Financial Data', icon: DollarSign,  bg: 'rgba(234,179,8,0.1)',   color: '#eab308', border: 'rgba(234,179,8,0.3)',   method: 'ai' },
  { type: 'demographic',  label: 'Demographics',   icon: Users,       bg: 'rgba(251,191,36,0.08)', color: '#f59e0b', border: 'rgba(251,191,36,0.25)', method: 'ai' },
  // ─── Phase 6: Vision detection types ─────────────────────────────────────
  { type: 'face_detected',    label: 'Faces',            icon: User,      bg: 'rgba(239,68,68,0.1)',  color: '#ef4444', border: 'rgba(239,68,68,0.3)',   method: 'vision' },
  { type: 'id_card_visible',  label: 'ID Card',          icon: CreditCard,bg: 'rgba(220,38,38,0.1)',  color: '#dc2626', border: 'rgba(220,38,38,0.3)',   method: 'vision' },
  { type: 'document_type',    label: 'Doc Type',         icon: FileImage, bg: 'rgba(99,102,241,0.1)', color: '#6366f1', border: 'rgba(99,102,241,0.3)',  method: 'vision' },
  { type: 'signature_visible',label: 'Signature',        icon: Key,       bg: 'rgba(168,85,247,0.1)', color: '#a855f7', border: 'rgba(168,85,247,0.3)',  method: 'vision' },
  { type: 'qr_barcode',       label: 'QR / Barcode',     icon: Hash,      bg: 'rgba(20,184,166,0.1)', color: '#14b8a6', border: 'rgba(20,184,166,0.3)',  method: 'vision' },
];

const ScoreRing = ({ score, risk }) => {
  const color = riskColor(risk);
  const r = 54; const circ = 2 * Math.PI * r;
  const offset = circ - (Math.min(score, 100) / 100) * circ;
  return (
    <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 130, height: 130 }}>
      <svg width="130" height="130" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="65" cy="65" r={r} fill="none" stroke="var(--border)" strokeWidth="9" />
        <circle cx="65" cy="65" r={r} fill="none" stroke={color} strokeWidth="9"
          strokeDasharray={circ} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1s ease', strokeLinecap: 'round' }} />
      </svg>
      <div style={{ position: 'absolute', textAlign: 'center' }}>
        <div style={{ fontSize: 28, fontWeight: 800, lineHeight: 1, color }}>{Math.round(score)}</div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>/ 100</div>
      </div>
    </div>
  );
};

export default function ScanPage() {
  const [searchParams] = useSearchParams();
  const urlScanId = searchParams.get('id');
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [blurring, setBlurring] = useState(false);
  const [zoomSrc, setZoomSrc] = useState(null);
  const [zoomLabel, setZoomLabel] = useState('');
  const [showText, setShowText] = useState(false);
  const [imageMode, setImageMode] = useState('original');

  // Persist scan in localStorage so navigation doesn't wipe it
  const [scan, setScanState] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null; } catch { return null; }
  });
  const setScan = (s) => {
    setScanState(s);
    if (s) localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    else localStorage.removeItem(STORAGE_KEY);
  };

  // Authenticated image blobs
  const originalSrc = useAuthImage(scan?.id, 'original');
  const blurredSrc  = useAuthImage(scan?.blurred_path ? scan.id : null, 'blurred');

  // Load scan by URL id
  useEffect(() => {
    if (urlScanId && (!scan || scan.id !== Number(urlScanId))) {
      setUploading(true);
      getScan(Number(urlScanId)).then(d => { setScan(d); setUploading(false); }).catch(() => setUploading(false));
    }
  }, [urlScanId]);

  const handleDrop = useCallback((e) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) {
      setFile(f);
      // If a scan is already showing, clear it so the new file is ready
      setScan(null);
      navigate('/scan', { replace: true });
    }
  }, [navigate]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const data = await uploadScan(file);
      setScan(data);
      setImageMode('original');
      navigate(`/scan?id=${data.id}`, { replace: true });
    } catch (e) {
      alert('Upload failed: ' + (e.response?.data?.detail || e.message));
    } finally { setUploading(false); }
  };

  const handleBlur = async () => {
    if (!scan) return;
    setBlurring(true);
    try {
      const updated = await blurScan(scan.id);
      setScan(updated);
      setImageMode('blurred');
    } catch (e) {
      alert('Blur failed: ' + (e.response?.data?.detail || e.message));
    } finally { setBlurring(false); }
  };

  const handleDownloadBlurred = async () => {
    if (!scan?.blurred_path) return;
    const token = localStorage.getItem('token');
    const r = await fetch(`${getBaseUrl()}/scans/${scan.id}/image/blurred`, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `blurred_${scan.filename}`; a.click();
    URL.revokeObjectURL(url);
  };

  const isImage = (s) => s && /\.(png|jpe?g)$/i.test(s.original_path || '');
  const displaySrc = imageMode === 'blurred' && blurredSrc ? blurredSrc : originalSrc;

  const emails    = scan?.findings?.filter(f => f.type === 'email') || [];
  const phones    = scan?.findings?.filter(f => f.type === 'phone') || [];
  const passwords = scan?.findings?.filter(f => f.type === 'password') || [];

  return (
    <div>
      {/* Equal-height two-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: scan ? '1fr 1fr' : '1fr', gap: 20, alignItems: 'start' }}>
        {/* LEFT — upload zone or image preview, fixed height to match right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {!scan ? (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
                <div className="section-title" style={{ margin: 0 }}>
                  <UploadCloud size={16} style={{ color: 'var(--accent)' }} /> Upload Document
                </div>
              </div>
              <div style={{ padding: 24 }}>
                {!file ? (
                  <div
                    className={`dropzone ${drag ? 'active' : ''}`}
                    onDrop={handleDrop}
                    onDragOver={e => { e.preventDefault(); setDrag(true); }}
                    onDragLeave={() => setDrag(false)}
                    onClick={() => document.getElementById('file-input-main').click()}
                  >
                    <div className="dropzone-icon"><UploadCloud size={28} style={{ color: 'var(--accent)' }} /></div>
                    <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>Drag & drop or click to browse</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Supports PNG, JPG, PDF, TXT, DOC, DOCX</div>
                    <input id="file-input-main" type="file" style={{ display: 'none' }} accept=".png,.jpg,.jpeg,.pdf,.txt,.doc,.docx,.bmp,.webp"
                      onChange={e => setFile(e.target.files[0])} />
                  </div>
                ) : (
                  <div style={{ background: 'var(--accent-light)', border: '1px solid rgba(32,101,209,0.2)', borderRadius: 'var(--radius-md)', padding: '16px 20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                        <FileImage size={32} style={{ color: 'var(--accent)' }} />
                        <div>
                          <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{file.name}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{(file.size / 1024).toFixed(1)} KB</div>
                        </div>
                      </div>
                      <button className="btn btn-secondary btn-sm" onClick={() => setFile(null)}><X size={14} /></button>
                    </div>
                    <div style={{ display: 'flex', gap: 10 }}>
                      <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setFile(null)}>Cancel</button>
                      <button className="btn btn-primary" style={{ flex: 2 }} onClick={handleUpload} disabled={uploading}>
                        {uploading ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Scanning...</> : '🔍 Start Scan'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* When scan result is shown — show compact banner + Add Another File */
            <>
              <div className="card" style={{ overflow:'hidden' }}>
                <div style={{ padding:'12px 18px', borderBottom:'1px solid var(--border)',
                  display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                  <span style={{ fontWeight:600, fontSize:13, color:'var(--text-primary)' }}>
                    {scan?.filename}
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => { setScan(null); setFile(null); navigate('/scan', { replace: true }); }}
                    style={{ display:'flex', alignItems:'center', gap:6 }}
                  >
                    <UploadCloud size={13}/> Scan Another File
                  </button>
                </div>
                {/* Mini drop zone */}
                <div
                  className={`dropzone ${drag ? 'active' : ''}`}
                  style={{ margin:'16px', padding:'14px', minHeight:'70px' }}
                  onDrop={e => { e.preventDefault(); setDrag(false); const f2=e.dataTransfer.files[0]; if(f2){setScan(null);setFile(f2);navigate('/scan',{replace:true});} }}
                  onDragOver={e => { e.preventDefault(); setDrag(true); }}
                  onDragLeave={() => setDrag(false)}
                  onClick={() => document.getElementById('file-input-extra').click()}
                >
                  <div style={{ fontSize:12, color:'var(--text-secondary)', textAlign:'center' }}>
                    <UploadCloud size={18} style={{ color:'var(--accent)', display:'block', margin:'0 auto 4px' }}/>
                    Drop another file here or <strong style={{ color:'var(--accent)' }}>click to browse</strong>
                  </div>
                  <input id="file-input-extra" type="file" style={{ display:'none' }} accept=".png,.jpg,.jpeg,.pdf,.txt,.doc,.docx,.bmp,.webp"
                    onChange={e => { const f2=e.target.files[0]; if(f2){setScan(null);setFile(f2);navigate('/scan',{replace:true});} }} />
                </div>
              </div>

              {/* Image preview — only for image scans */}
              {isImage(scan) && (
                <div className="card" style={{ overflow:'hidden', minHeight:280 }}>
                  <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <span style={{ fontWeight:600, fontSize:13, color:'var(--text-primary)' }}>
                      {imageMode==='blurred'&&blurredSrc ? '🔵 Blurred Image' : '🖼️ Original Image'}
                    </span>
                    <div style={{ display:'flex', gap:8 }}>
                      {scan.blurred_path && (
                        <button className="btn btn-secondary btn-sm" onClick={() => setImageMode(m => m==='blurred'?'original':'blurred')}>
                          Show {imageMode==='blurred'?'Original':'Blurred'}
                        </button>
                      )}
                      <button className="btn btn-secondary btn-sm" onClick={() => { setZoomSrc(displaySrc); setZoomLabel('Image Preview'); }}><ZoomIn size={14}/></button>
                      {imageMode==='blurred'&&blurredSrc&&<button className="btn btn-secondary btn-sm" onClick={handleDownloadBlurred}><Download size={14}/></button>}
                    </div>
                  </div>
                  <div style={{ minHeight:220, display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg-base)' }}>
                    {displaySrc
                      ? <img src={displaySrc} alt="Scan" className="img-zoomable"
                          style={{ maxWidth:'100%', maxHeight:280, objectFit:'contain', padding:8 }}
                          onClick={() => { setZoomSrc(displaySrc); setZoomLabel(imageMode==='blurred'&&blurredSrc?'🔵 Blurred Image':'🖼️ Original Image'); }}/>
                      : <div style={{ textAlign:'center', color:'var(--text-muted)' }}>
                          <div className="spinner" style={{ margin:'0 auto 8px', borderColor:'var(--border)', borderTopColor:'var(--accent)', width:28, height:28 }}/>
                          <div style={{ fontSize:12 }}>Loading image...</div>
                        </div>
                    }
                  </div>
                </div>
              )}
            </>
          )}

          {/* Extracted Text */}
          {scan?.extracted_text && (
            <div className="card" style={{ overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', cursor: 'pointer', alignItems: 'center' }}
                onClick={() => setShowText(s => !s)}>
                <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>📝 Extracted Text (OCR)</span>
                {showText ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
              {showText && (
                <pre style={{ padding: 16, fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflowY: 'auto', lineHeight: 1.7, background: 'var(--bg-base)' }}>
                  {scan.extracted_text}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* RIGHT: Results — same min-height as image panel */}
        {scan && (
          <div className="card" style={{ overflow: 'hidden', minHeight: 480 }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="section-title" style={{ margin: 0 }}>
                <Shield size={16} style={{ color: 'var(--accent)' }} /> Scan Results
                <span style={{ fontWeight: 400, color: 'var(--text-secondary)', fontSize: 12 }}> — {scan.filename}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {/* AI engine badge */}
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  fontSize: 10, fontWeight: 700, letterSpacing: '0.04em',
                  color: '#22c55e', background: 'rgba(34,197,94,0.08)',
                  border: '1px solid rgba(34,197,94,0.2)',
                  borderRadius: 5, padding: '2px 7px',
                }}>🤖 AI Powered</span>
                {/* Clear button */}
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => { setScan(null); setFile(null); navigate('/scan', { replace: true }); }}
                  title="Clear scan results"
                >
                  <X size={13} /> Clear
                </button>
              </div>
            </div>
            <div style={{ padding: '20px 24px' }}>
              {/* Score + Risk */}
              <div style={{ display: 'flex', gap: 24, alignItems: 'center', marginBottom: 20, paddingBottom: 20, borderBottom: '1px solid var(--border)' }}>
                <ScoreRing score={scan.score} risk={scan.risk_level} />
                <div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>Risk Level</div>
                  <span
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      padding: '5px 14px', borderRadius: 20,
                      fontSize: 12, fontWeight: 800, letterSpacing: '0.05em',
                      background: scan.risk_level === 'CRITICAL' ? 'rgba(220,38,38,0.15)'
                                : scan.risk_level === 'HIGH'     ? 'var(--danger-bg)'
                                : scan.risk_level === 'MEDIUM'   ? 'var(--warning-bg)'
                                : 'var(--success-bg)',
                      color: riskColor(scan.risk_level),
                      border: `1px solid ${riskColor(scan.risk_level)}44`
                    }}
                  >
                    {scan.risk_level === 'CRITICAL' ? '🔴' : scan.risk_level === 'HIGH' ? '🟠' : scan.risk_level === 'MEDIUM' ? '🟡' : '🟢'}
                    {scan.risk_level}
                  </span>
                  <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                    <strong style={{ color: 'var(--text-primary)' }}>{scan.findings?.length || 0}</strong> sensitive item(s) detected
                  </div>
                  <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>{new Date(scan.upload_date).toLocaleString()}</div>
                </div>
              </div>

              {/* Phase 6 — Vision Analysis Badge */}
              {(scan.vision_doc_type || scan.vision_face_count > 0 || scan.vision_is_id_doc) && (
                <div style={{ marginBottom: 16 }}>
                  <VisionBadge
                    docType={scan.vision_doc_type}
                    faceCount={scan.vision_face_count || 0}
                    isIdDoc={scan.vision_is_id_doc}
                  />
                </div>
              )}

              {/* Document Type Badge — always shown when AI/keyword classifier identifies the file type */}
              {(() => {
                const label = scan.ai_doc_type_label;
                const conf  = scan.ai_doc_confidence;
                // Show for any identified type with ≥45% confidence (covers keyword fallback too)
                if (!label || label === 'General Document') return null;
                if (conf != null && conf < 0.45) return null;

                // Icon and colour per document type
                const typeStyles = {
                  'Aadhaar Card':                     { icon: '🪪', color: '#ef4444', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.25)'   },
                  'PAN Card':                         { icon: '💳', color: '#dc2626', bg: 'rgba(220,38,38,0.08)',   border: 'rgba(220,38,38,0.25)'   },
                  'Passport / Travel Document':       { icon: '🛂', color: '#7c3aed', bg: 'rgba(124,58,237,0.08)', border: 'rgba(124,58,237,0.25)'  },
                  'Bank Statement':                   { icon: '🏦', color: '#2563eb', bg: 'rgba(37,99,235,0.08)',   border: 'rgba(37,99,235,0.25)'   },
                  'Salary Slip / Payslip':            { icon: '💰', color: '#d97706', bg: 'rgba(217,119,6,0.08)',   border: 'rgba(217,119,6,0.25)'   },
                  'Resume / CV':                      { icon: '📄', color: '#0891b2', bg: 'rgba(8,145,178,0.08)',   border: 'rgba(8,145,178,0.25)'   },
                  'Medical / Health Record':          { icon: '🏥', color: '#16a34a', bg: 'rgba(22,163,74,0.08)',   border: 'rgba(22,163,74,0.25)'   },
                  'Project Report / Academic Document':{ icon: '📚', color: '#6366f1', bg: 'rgba(99,102,241,0.08)', border: 'rgba(99,102,241,0.25)'  },
                  'ML / Data Science Code or Lab Manual':{ icon: '🧪', color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.25)' },
                  'Driving License':                  { icon: '🚗', color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.25)'  },
                  'Invoice / Bill':                   { icon: '🧾', color: '#64748b', bg: 'rgba(100,116,139,0.08)', border: 'rgba(100,116,139,0.25)' },
                  'Marks Card / ID Card':             { icon: '🎓', color: '#059669', bg: 'rgba(5,150,105,0.08)',   border: 'rgba(5,150,105,0.25)'   },
                  'Screenshot — Login / Authentication':{ icon: '🔒', color: '#dc2626', bg: 'rgba(220,38,38,0.08)', border: 'rgba(220,38,38,0.25)'  },
                  'Screenshot — Chat / Conversation': { icon: '💬', color: '#0284c7', bg: 'rgba(2,132,199,0.08)',   border: 'rgba(2,132,199,0.25)'  },
                  'Screenshot — Social Media':        { icon: '📱', color: '#7c3aed', bg: 'rgba(124,58,237,0.08)', border: 'rgba(124,58,237,0.25)'  },
                };
                const style = typeStyles[label] || { icon: '📁', color: '#64748b', bg: 'rgba(100,116,139,0.08)', border: 'rgba(100,116,139,0.25)' };
                return (
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    background: style.bg, border: `1px solid ${style.border}`,
                    borderRadius: 10, padding: '10px 14px', marginBottom: 16,
                  }}>
                    <span style={{ fontSize: 20 }}>{style.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: style.color, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 2 }}>
                        Document Type Detected
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                        {label}
                      </div>
                    </div>
                    {conf != null && (
                      <span style={{
                        fontSize: 11, fontWeight: 800, color: style.color,
                        background: style.bg, border: `1px solid ${style.border}`,
                        borderRadius: 6, padding: '2px 8px',
                      }}>
                        {Math.round(conf * 100)}%
                      </span>
                    )}
                  </div>
                );
              })()}

              {/* Findings — all types with AI/Vision confidence */}
              <div style={{ marginBottom: 20, minHeight: 60, maxHeight: 300, overflowY: 'auto' }}>

                {scan.findings?.length > 0 ? (
                  FINDING_TYPES
                    .map(ft => ({ ...ft, items: scan.findings.filter(f => f.type === ft.type) }))
                    .filter(g => g.items.length > 0)
                    .map(group => {
                      const Icon = group.icon;
                      // Average AI confidence for this group
                      const avgConf = group.items
                        .map(f => f.ai_confidence)
                        .filter(c => c != null)
                        .reduce((sum, c, _, arr) => sum + c / arr.length, 0);
                      return (
                        <div key={group.type} style={{ marginBottom: 14 }}>
                          <div style={{ fontSize: 11, fontWeight: 700, color: group.color, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5, display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Icon size={11} /> {group.label} ({group.items.length})
                            {avgConf > 0 && <AIBadge confidence={avgConf} small />}
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                            {group.items.map((f, i) => (
                              <span key={i} className="finding-tag" style={{ background: group.bg, color: group.color, border: `1px solid ${group.border}`, display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'nowrap' }}>
                                <Icon size={10} />
                                <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.value}</span>
                                {f.ai_confidence != null && (
                                  <span style={{ fontSize: 9, opacity: 0.75 }}>{Math.round(f.ai_confidence * 100)}%</span>
                                )}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })
                ) : (
                  <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--success)', fontSize: 13, fontWeight: 600 }}>
                    ✅ No sensitive data detected
                  </div>
                )}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {isImage(scan) && !scan.blurred_path && scan.findings?.length > 0 && (
                  <button className="btn btn-primary" style={{ width: '100%' }} onClick={handleBlur} disabled={blurring}>
                    {blurring ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Applying Blur...</> : '🔵 Blur Sensitive Data'}
                  </button>
                )}
                {scan.blurred_path && (
                  <button className="btn btn-success" style={{ width: '100%' }} onClick={handleDownloadBlurred}>
                    <Download size={14} /> Download Blurred Image
                  </button>
                )}
                <div style={{ display: 'flex', gap: 10 }}>
                  <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => navigate(`/report?id=${scan.id}`)}>📄 Report</button>
                  <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => navigate(`/recommendations?id=${scan.id}`)}>💡 Tips</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Lightbox */}
      <Lightbox
        src={zoomSrc}
        label={zoomLabel}
        onClose={() => { setZoomSrc(null); setZoomLabel(''); }}
      />
    </div>
  );
}
