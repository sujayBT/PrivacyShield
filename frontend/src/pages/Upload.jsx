import React, { useState } from 'react';
import { uploadScan, blurScan } from '../api';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, AlertCircle, FileImage, ShieldAlert } from 'lucide-react';

const Upload = () => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [blurring, setBlurring] = useState(false);
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setScanResult(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const data = await uploadScan(file);
      setScanResult(data);
    } catch (err) {
      console.error(err);
      alert('Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const handleBlur = async () => {
    if (!scanResult) return;
    setBlurring(true);
    try {
      const updatedScan = await blurScan(scanResult.id);
      setScanResult(updatedScan);
      alert('Image blurred successfully! Check the backend/uploads folder.');
    } catch (err) {
      console.error(err);
      alert('Blurring failed');
    } finally {
      setBlurring(false);
    }
  };

  return (
    <div className="container animate-fade-in">
      <h2 style={{ marginBottom: '24px' }}>Scan New Document</h2>

      <div style={{ display: 'grid', gridTemplateColumns: scanResult ? '1fr 1fr' : '1fr', gap: '32px' }}>
        
        {/* Upload Panel */}
        <div className="glass-panel" style={{ padding: '32px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
          {!file ? (
            <>
              <div style={{ width: '80px', height: '80px', borderRadius: '50%', backgroundColor: 'rgba(88, 166, 255, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '24px' }}>
                <UploadIcon size={40} color="var(--accent-color)" />
              </div>
              <h3 style={{ marginBottom: '16px' }}>Upload File</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '24px', fontSize: '14px' }}>Supports PNG, JPG, and PDF files</p>
              
              <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
                Browse Files
                <input type="file" style={{ display: 'none' }} onChange={handleFileChange} accept=".png,.jpg,.jpeg,.pdf" />
              </label>
            </>
          ) : (
            <>
              <FileImage size={48} color="var(--accent-color)" style={{ marginBottom: '16px' }} />
              <h3 style={{ marginBottom: '8px' }}>{file.name}</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '24px', fontSize: '14px' }}>{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              
              {!scanResult && (
                <div style={{ display: 'flex', gap: '16px' }}>
                  <button className="btn" onClick={() => setFile(null)}>Cancel</button>
                  <button className="btn btn-primary" onClick={handleUpload} disabled={loading}>
                    {loading ? 'Scanning...' : 'Start Scan'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Results Panel */}
        {scanResult && (
          <div className="glass-panel animate-fade-in" style={{ padding: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
              <ShieldAlert size={28} color={scanResult.risk_level === 'HIGH' ? 'var(--danger-color)' : scanResult.risk_level === 'MEDIUM' ? 'var(--warning-color)' : 'var(--success-color)'} />
              <h2>Scan Results</h2>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '32px', paddingBottom: '24px', borderBottom: '1px solid var(--panel-border)' }}>
              <div>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Privacy Score</div>
                <div style={{ fontSize: '36px', fontWeight: 'bold' }}>{scanResult.score}<span style={{ fontSize: '16px', color: 'var(--text-secondary)' }}>/100</span></div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Risk Level</div>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: scanResult.risk_level === 'HIGH' ? 'var(--danger-color)' : scanResult.risk_level === 'MEDIUM' ? 'var(--warning-color)' : 'var(--success-color)' }}>{scanResult.risk_level}</div>
              </div>
            </div>

            <h4 style={{ marginBottom: '16px' }}>Detected Sensitive Data</h4>
            {scanResult.findings.length === 0 ? (
              <p style={{ color: 'var(--success-color)', fontSize: '14px' }}>No sensitive data found.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, marginBottom: '32px', maxHeight: '200px', overflowY: 'auto' }}>
                {scanResult.findings.map(finding => (
                  <li key={finding.id} style={{ padding: '8px 12px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '6px', marginBottom: '8px', fontSize: '14px', display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: '600', textTransform: 'uppercase', fontSize: '12px', color: 'var(--text-secondary)' }}>{finding.type}</span>
                    <span>{finding.value}</span>
                  </li>
                ))}
              </ul>
            )}

            <div style={{ display: 'flex', gap: '16px' }}>
              <button className="btn" onClick={() => navigate('/dashboard')} style={{ flex: 1, justifyContent: 'center' }}>Back to Dashboard</button>
              {scanResult.findings.length > 0 && scanResult.original_path.match(/\.(jpeg|jpg|png)$/i) && (
                <button className="btn btn-primary" onClick={handleBlur} disabled={blurring || scanResult.blurred_path} style={{ flex: 1, justifyContent: 'center', backgroundColor: scanResult.blurred_path ? 'var(--success-color)' : '' }}>
                  {scanResult.blurred_path ? 'Data Blurred' : blurring ? 'Blurring...' : 'Blur Sensitive Data'}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Upload;
