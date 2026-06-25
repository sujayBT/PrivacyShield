import React, { useEffect, useState, useCallback, useRef } from 'react';
import { getScans, blurScan, uploadScan, getBaseUrl } from '../api';
import { Layers, Download, ImageOff, Info, X, ZoomIn, Upload, EyeOff, User } from 'lucide-react';
import { useAuthImage } from '../hooks/useAuthImage';
import Lightbox from '../components/Lightbox';

const BLUR_STORAGE_KEY = 'blurEngineState';

// ── Image Panel ──────────────────────────────────────────────────────────────
const ImagePanel = ({ scanId, type, label, icon, placeholder, onZoom }) => {
  const src = useAuthImage(scanId, type);
  return (
    <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{label}</span>
        {src && (
          <button className="btn btn-secondary btn-sm" style={{ marginLeft: 'auto' }} onClick={() => onZoom(src, label)}>
            <ZoomIn size={13} /> Zoom
          </button>
        )}
      </div>
      <div style={{ flex: 1, minHeight: 380, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-base)' }}>
        {src ? (
          <img
            src={src}
            alt={label}
            className="img-zoomable"
            style={{ maxWidth: '100%', maxHeight: 420, objectFit: 'contain', display: 'block', padding: 8 }}
            onClick={() => onZoom(src, label)}
          />
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>
            <ImageOff size={40} style={{ marginBottom: 12, opacity: 0.35, display: 'block', margin: '0 auto 12px' }} />
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>{placeholder}</div>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Main Blur Page ────────────────────────────────────────────────────────────
export default function BlurPage() {
  const [scans, setScans]               = useState([]);
  const [blurring, setBlurring]         = useState(false);       // text PII blur in progress
  const [blurringFaces, setBlurringFaces] = useState(false);     // face blur in progress
  const [uploading, setUploading]       = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [dragOver, setDragOver]         = useState(false);
  const fileInputRef = useRef(null);

  // Persist selected scan across page reloads
  const [selectedId, setSelectedId] = useState(() => {
    try { return localStorage.getItem(`${BLUR_STORAGE_KEY}_id`) || ''; } catch { return ''; }
  });
  const [scanMap, setScanMap] = useState(() => {
    try { return JSON.parse(localStorage.getItem(`${BLUR_STORAGE_KEY}_map`)) || {}; } catch { return {}; }
  });

  const persistState = useCallback((id, map) => {
    try {
      localStorage.setItem(`${BLUR_STORAGE_KEY}_id`, id);
      localStorage.setItem(`${BLUR_STORAGE_KEY}_map`, JSON.stringify(map));
    } catch {}
  }, []);

  const clearState = () => {
    setSelectedId('');
    setScanMap({});
    localStorage.removeItem(`${BLUR_STORAGE_KEY}_id`);
    localStorage.removeItem(`${BLUR_STORAGE_KEY}_map`);
  };

  // Lightbox
  const [lightboxSrc, setLightboxSrc]     = useState(null);
  const [lightboxLabel, setLightboxLabel] = useState('');
  const openZoom  = (src, label) => { setLightboxSrc(src); setLightboxLabel(label); };
  const closeZoom = ()           => { setLightboxSrc(null); setLightboxLabel(''); };

  // Load scans list
  const refreshScans = useCallback(() => {
    return getScans().then(data => {
      const imageScans = data.filter(s => /\.(png|jpe?g)$/i.test(s.original_path || ''));
      setScans(imageScans);
      setScanMap(prev => {
        const updated = { ...prev };
        imageScans.forEach(s => { updated[s.id] = { ...prev[s.id], ...s }; });
        return updated;
      });
      return imageScans;
    });
  }, []);

  useEffect(() => { refreshScans(); }, [refreshScans]);

  const activeScan = selectedId ? scanMap[Number(selectedId)] : null;

  // How many faces were detected in this scan
  const faceCount = (() => {
    if (!activeScan) return 0;
    if (typeof activeScan.vision_face_count === 'number') {
      return activeScan.vision_face_count;
    }
    if (!activeScan.findings) return 0;
    const f = activeScan.findings.find(f => f.type === 'face_detected');
    if (!f) return 0;
    const m = f.value?.match(/(\d+)\s+face/);
    return m ? parseInt(m[1]) : 1;
  })();

  // ── Handlers ────────────────────────────────────────────────────────────────
  const handleSelect = (e) => {
    const id = e.target.value;
    setSelectedId(id);
    if (id && !scanMap[Number(id)]) {
      const found = scans.find(s => s.id === Number(id));
      if (found) {
        const newMap = { ...scanMap, [found.id]: found };
        setScanMap(newMap);
        persistState(id, newMap);
      }
    } else {
      persistState(id, scanMap);
    }
  };

  const handleUploadFile = async (file) => {
    if (!file) return;
    if (!/\.(png|jpe?g)$/i.test(file.name)) { alert('Please upload a PNG or JPG image file.'); return; }
    setUploading(true);
    setUploadProgress(`Uploading "${file.name}"...`);
    try {
      setUploadProgress(`Scanning "${file.name}" for sensitive data...`);
      const result = await uploadScan(file);
      const newMap = { ...scanMap, [result.id]: result };
      setScanMap(newMap);
      setScans(prev => [result, ...prev]);
      setSelectedId(String(result.id));
      persistState(String(result.id), newMap);
      refreshScans();
      setUploadProgress('');
    } catch (err) {
      alert('Upload failed: ' + (err.response?.data?.detail || err.message));
      setUploadProgress('');
    } finally { setUploading(false); }
  };

  const handleFileInput = (e) => {
    const file = e.target.files?.[0];
    if (file) handleUploadFile(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDragOver  = (e) => { e.preventDefault(); e.stopPropagation(); setDragOver(true); };
  const handleDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); };
  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation(); setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) handleUploadFile(file);
  };

  // Shared blur runner — withFaces controls whether OpenCV face boxes are applied
  const runBlur = async (withFaces, setLoading) => {
    if (!activeScan) return;
    setLoading(true);
    try {
      const updated = await blurScan(activeScan.id, withFaces);
      const newMap = { ...scanMap, [updated.id]: updated };
      setScanMap(newMap);
      persistState(selectedId, newMap);
      // Force image panel to re-mount and reload
      const curId = selectedId;
      setSelectedId('');
      setTimeout(() => setSelectedId(curId), 50);
    } catch (e) {
      alert('Blur failed: ' + (e.response?.data?.detail || e.message));
    } finally { setLoading(false); }
  };

  // "Apply Smart Blur" — redacts text PII only (names, IDs, Aadhaar, DOB, emails…)
  const handleBlur      = () => runBlur(false, setBlurring);

  // "Blur Faces" — re-runs with OpenCV face bounding boxes included
  const handleBlurFaces = () => runBlur(true, setBlurringFaces);

  const handleDownload = async () => {
    if (!activeScan?.blurred_path) return;
    const token = localStorage.getItem('token');
    const r = await fetch(`${getBaseUrl()}/scans/${activeScan.id}/image/blurred`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `blurred_${activeScan.filename}`;
    a.click(); URL.revokeObjectURL(url);
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div>
      <Lightbox src={lightboxSrc} label={lightboxLabel} onClose={closeZoom} />
      <input ref={fileInputRef} type="file" accept=".png,.jpg,.jpeg" style={{ display: 'none' }} onChange={handleFileInput} />

      {/* ── Control Panel ──────────────────────────────────────────────────── */}
      <div className="card" style={{ padding: '20px 24px', marginBottom: 20 }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 6 }}>
          <div className="section-title" style={{ margin: 0 }}>
            <Layers size={16} style={{ color: 'var(--accent)' }} /> Blur Engine
          </div>
          {activeScan && (
            <button className="btn btn-danger btn-sm" onClick={clearState} title="Clear selection">
              <X size={13} /> Clear
            </button>
          )}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 18 }}>
          Select a scanned image or upload a new one to redact sensitive regions.
          {activeScan && <span style={{ color: 'var(--accent)', fontWeight: 600 }}> Your selection is saved.</span>}
        </p>

        {/* Row 1 — Select + Upload */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 14 }}>
          <select className="input" style={{ maxWidth: 360, flex: '1 1 240px' }} value={selectedId} onChange={handleSelect}>
            <option value="">— Select a scanned image —</option>
            {scans.map(s => (
              <option key={s.id} value={s.id}>
                #{s.id} — {s.filename} ({s.risk_level}){s.blurred_path ? ' ✓ Blurred' : ''}
              </option>
            ))}
          </select>

          <button
            className="btn"
            style={{ background: 'linear-gradient(135deg,rgba(88,166,255,.12),rgba(139,92,246,.12))', border: '1px dashed var(--accent)', color: 'var(--accent)', fontWeight: 600 }}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading
              ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2, borderColor: 'rgba(88,166,255,.3)', borderTopColor: 'var(--accent)' }} /> Uploading...</>
              : <><Upload size={14} /> Upload New Image</>}
          </button>
        </div>

        {/* Row 2 — Action buttons */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>

          {/* ① Redact Sensitive Text — text PII only */}
          <button
            className="btn btn-primary"
            onClick={handleBlur}
            disabled={!activeScan || blurring || blurringFaces}
            title="Redacts names, IDs, Aadhaar, dates, emails, passwords and more"
          >
            {blurring
              ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,.3)', borderTopColor: '#fff' }} /> Redacting...</>
              : <><EyeOff size={14} /> Redact Sensitive Text</>}
          </button>

          {/* ② Also Blur Faces — only appears when faces are detected */}
          {activeScan && faceCount > 0 && (
            <button
              className="btn"
              onClick={handleBlurFaces}
              disabled={blurring || blurringFaces}
              title={`Optional: blur the ${faceCount} face${faceCount > 1 ? 's' : ''} detected in this image`}
              style={{
                background: 'linear-gradient(135deg,rgba(251,113,133,.15),rgba(239,68,68,.1))',
                border: '1px solid rgba(251,113,133,.55)',
                color: '#fb7185',
                fontWeight: 600,
              }}
            >
              {blurringFaces
                ? <><div className="spinner" style={{ borderColor: 'rgba(251,113,133,.3)', borderTopColor: '#fb7185', width: 14, height: 14, borderWidth: 2 }} /> Blurring Faces...</>
                : <><User size={14} /> Also Blur Face{faceCount > 1 ? 's' : ''}&nbsp;<span style={{ opacity: 0.7, fontWeight: 400 }}>({faceCount} found)</span></>}
            </button>
          )}

          {/* ③ Download */}
          {activeScan?.blurred_path && (
            <button className="btn btn-success" onClick={handleDownload}>
              <Download size={14} /> Download Blurred
            </button>
          )}
        </div>

        {/* Face detected hint banner */}
        {activeScan && faceCount > 0 && (
          <div style={{
            marginTop: 14, padding: '10px 14px', borderRadius: 8,
            background: 'linear-gradient(135deg,rgba(251,113,133,.08),rgba(239,68,68,.05))',
            border: '1px solid rgba(251,113,133,.25)',
            display: 'flex', alignItems: 'center', gap: 10,
            fontSize: 13, color: '#fb7185',
          }}>
            <User size={15} />
            <span>
              <strong>{faceCount} face{faceCount > 1 ? 's' : ''} found</strong> in this image.
              {' '}Hiding faces is <strong>optional</strong> — use <em>"Also Blur Face{faceCount > 1 ? 's' : ''}"</em> only if you want to hide them too.
            </span>
          </div>
        )}

        {/* Upload progress */}
        {uploadProgress && (
          <div className="alert alert-info" style={{ marginTop: 14, marginBottom: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2, borderColor: 'rgba(88,166,255,.3)', borderTopColor: 'var(--accent)' }} />
            {uploadProgress}
          </div>
        )}

        {/* Ready banner */}
        {activeScan?.blurred_path && (
          <div className="alert alert-success" style={{ marginTop: 14, marginBottom: 0 }}>
            <Info size={14} /> Blurred image is ready — click any image to zoom, or download above.
          </div>
        )}
      </div>

      {/* ── Image Panels ───────────────────────────────────────────────────── */}
      {activeScan ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'stretch' }}>
          <ImagePanel
            key={`orig-${activeScan.id}`}
            scanId={activeScan.id}
            type="original"
            label="Original Image"
            icon="🖼️"
            placeholder="Original image not available"
            onZoom={openZoom}
          />
          <ImagePanel
            key={`blur-${activeScan.id}-${activeScan.blurred_path || 'none'}`}
            scanId={activeScan.blurred_path ? activeScan.id : null}
            type="blurred"
            label="Blurred Image"
            icon="🔵"
            placeholder={activeScan.blurred_path ? 'Loading blurred image...' : 'Click "Redact Sensitive Text" to hide private info in this image'}
            onZoom={openZoom}
          />
        </div>
      ) : (
        /* ── Drop Zone ─────────────────────────────────────────────────────── */
        <div
          className="card"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
          style={{
            padding: '56px 32px', textAlign: 'center', color: 'var(--text-secondary)',
            cursor: uploading ? 'wait' : 'pointer',
            border: dragOver ? '2px dashed var(--accent)' : '2px dashed transparent',
            background: dragOver ? 'linear-gradient(135deg,rgba(88,166,255,.08),rgba(139,92,246,.08))' : 'var(--bg-card)',
            transition: 'all 0.2s ease', borderRadius: 12,
          }}
        >
          {uploading ? (
            <>
              <div className="spinner" style={{ width: 48, height: 48, borderWidth: 3, margin: '0 auto 20px', borderColor: 'rgba(88,166,255,.2)', borderTopColor: 'var(--accent)' }} />
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>{uploadProgress || 'Processing...'}</div>
              <div style={{ fontSize: 13 }}>This may take a moment depending on file size</div>
            </>
          ) : (
            <>
              <div style={{ width: 80, height: 80, borderRadius: '50%', margin: '0 auto 20px', background: 'linear-gradient(135deg,rgba(88,166,255,.15),rgba(139,92,246,.15))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Upload size={36} style={{ color: 'var(--accent)' }} />
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>Upload an Image to Blur</div>
              <div style={{ fontSize: 13, marginBottom: 20, maxWidth: 420, margin: '0 auto 20px' }}>
                Drag and drop a PNG or JPG image here, or click to browse.
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                {['PNG', 'JPG', 'JPEG'].map(ext => (
                  <span key={ext} style={{ padding: '4px 12px', borderRadius: 20, fontSize: 11, fontWeight: 600, background: 'rgba(88,166,255,.1)', color: 'var(--accent)' }}>{ext}</span>
                ))}
              </div>
              {scans.length > 0 && (
                <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
                  Or select a previously scanned image from the dropdown above • {scans.length} image{scans.length !== 1 ? 's' : ''} available
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
