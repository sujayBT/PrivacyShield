import axios from 'axios';

let backendPort = 8000;
if (window.electronAPI && typeof window.electronAPI.getBackendPortSync === 'function') {
  try {
    const port = window.electronAPI.getBackendPortSync();
    if (port) backendPort = port;
  } catch (err) {
    console.error("Failed to get backend port synchronously:", err);
  }
}

export const getBaseUrl = () => `http://127.0.0.1:${backendPort}/api`;

const api = axios.create({ baseURL: getBaseUrl() });
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || '';
    // Skip redirect when the 401 comes from login/change-password themselves
    const isAuthCall = url.includes('/auth/login') || url.includes('/auth/change-password');
    if (err.response?.status === 401 && !isAuthCall) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// Auth
export const login = (username, password) => {
  const f = new URLSearchParams({ username, password });
  return api.post('/auth/login', f, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }).then(r => r.data);
};
export const register = (username, password) => api.post('/auth/register', { username, password }).then(r => r.data);
export const changePassword = (username, old_password, new_password) =>
  api.post('/auth/change-password', { username, old_password, new_password }).then(r => r.data);


// Scans
export const getScans = () => api.get('/scans/').then(r => r.data);
export const getScan = (id) => api.get(`/scans/${id}`).then(r => r.data);
export const uploadScan = (file) => {
  const fd = new FormData(); fd.append('file', file);
  return api.post('/scans/upload', fd).then(r => r.data);
};
export const blurScan = (id, blurFaces = true) => api.post(`/scans/${id}/blur?blur_faces=${blurFaces}`).then(r => r.data);
export const getRecommendations  = (id)  => api.get(`/scans/${id}/recommendations`).then(r => r.data);
export const getRemediationPlan        = (id)  => api.get(`/scans/${id}/remediation`).then(r => r.data);
export const generateRemediationReport = (id)  => api.post(`/scans/${id}/report/remediation`, {}, { responseType: 'blob' }).then(r => r.data);
export const generateReport             = (id)  => api.post(`/scans/${id}/report`, {}, { responseType: 'blob' }).then(r => r.data);

export const generateSensitiveSummary  = (id) => api.post(`/scans/${id}/report/sensitive-summary`,  {}, { responseType: 'blob' }).then(r => r.data);
export const generateMetadataReport    = (id) => api.post(`/scans/${id}/report/metadata`,           {}, { responseType: 'blob' }).then(r => r.data);
export const generateAttackSimulation  = (id) => api.post(`/scans/${id}/report/attack-simulation`,  {}, { responseType: 'blob' }).then(r => r.data);
export const generateScoreHistory      = ()   => api.post(`/scans/report/score-history`,            {}, { responseType: 'blob' }).then(r => r.data);
export const generateBatchReport       = ()   => api.post(`/scans/report/batch`,                    {}, { responseType: 'blob' }).then(r => r.data);

// URL Scanning (Phase 5)
export const scanUrl          = (url) => api.post('/url-scan/scan', { url }).then(r => r.data);
export const getUrlScanHistory= ()    => api.get('/url-scan/history').then(r => r.data);
export const deleteUrlScan    = (id)  => api.delete(`/url-scan/history/${id}`);
export const getAiInfo     = () => api.get('/scans/ai-info').then(r => r.data);
export const getVisionInfo = () => api.get('/scans/vision-info').then(r => r.data);

// Phase 7 — Cloud Scanning
export const cloudScanLink    = (url)   => api.post('/cloud/scan-link', { url }).then(r => r.data);
export const cloudBatchUpload = (files) => {
  const fd = new FormData();
  files.forEach(f => fd.append('files', f));
  return api.post('/cloud/batch-upload', fd).then(r => r.data);
};
export const getCloudHistory  = ()      => api.get('/cloud/history').then(r => r.data);
export const getCloudScanDetail = (id)  => api.get(`/cloud/history/${id}`).then(r => r.data);

// Phase 8 — Screenshot Monitor
export const startSession      = ()          => api.post('/monitor/session/start').then(r => r.data);
export const stopSession       = (id)        => api.post(`/monitor/session/stop/${id}`).then(r => r.data);
export const deleteSession     = (id)        => api.delete(`/monitor/sessions/${id}`).then(r => r.data);
export const getSessions       = ()          => api.get('/monitor/sessions').then(r => r.data);
export const getSessionDetail  = (id)        => api.get(`/monitor/sessions/${id}`).then(r => r.data);
export const getAllAlerts       = ()          => api.get('/monitor/alerts').then(r => r.data);
export const analyzeFrame      = (formData)  => api.post('/monitor/analyze', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
}).then(r => r.data);

// Phase 9 — Social Media Scanner
export const socialScan              = (url)  => api.post('/social/scan', { url }).then(r => r.data);
export const getSocialHistory        = ()     => api.get('/social/history').then(r => r.data);
export const getSocialDetail         = (id)   => api.get(`/social/history/${id}`).then(r => r.data);
export const deleteSocialScan        = (id)   => api.delete(`/social/history/${id}`).then(r => r.data);
export const clearAllSocialHistory   = ()     => api.delete('/social/history').then(r => r.data);
export const purgeLegacySocialScans  = ()     => api.delete('/social/history-purge-legacy').then(r => r.data);

export const metadataScan       = (file) => {
  const fd = new FormData(); fd.append('file', file);
  return api.post('/metadata/scan', fd).then(r => r.data);
};
export const getMetadataForScan = (id)  => api.get(`/metadata/scan/${id}`).then(r => r.data);
export const getMetadataHistory = ()    => api.get('/metadata/history').then(r => r.data);
export const metadataPdfReport  = (id)  => api.post(`/metadata/scan/${id}/report`, {}, { responseType: 'blob' }).then(r => r.data);
export const metadataClean      = (file) => {
  const fd = new FormData(); fd.append('file', file);
  return api.post('/metadata/clean', fd, { responseType: 'blob' }).then(r => r.data);
};


// Phase 11 — Attack Simulation
export const simulateFromScan    = (scanId)   => api.post(`/attack/simulate/scan/${scanId}`).then(r => r.data);
export const simulateAggregate   = ()          => api.get('/attack/simulate/aggregate').then(r => r.data);
export const simulateCustom      = (payload)   => api.post('/attack/simulate/custom', payload).then(r => r.data);
export const getAttackScenarios  = ()          => api.get('/attack/scenarios').then(r => r.data);
export const getAttackScans      = ()          => api.get('/attack/scans').then(r => r.data);

// Phase 12 — Score History Tracker
export const getHistoryTimeline  = (days=30)   => api.get(`/history/timeline?days=${days}`).then(r => r.data);
export const getHistorySummary   = ()           => api.get('/history/summary').then(r => r.data);
export const getHistoryBySource  = ()           => api.get('/history/by-source').then(r => r.data);
export const getHistoryRecent    = (limit=50)   => api.get(`/history/recent?limit=${limit}`).then(r => r.data);
export const getHistoryDailyAvg  = (days=30)    => api.get(`/history/daily-avg?days=${days}`).then(r => r.data);

// Phase 13 — Batch Screenshot Scanner
export const batchScanUpload     = (formData)   => api.post('/batch-scan/upload', formData, { headers:{'Content-Type':'multipart/form-data'} }).then(r => r.data);
export const getBatchJobs        = ()            => api.get('/batch-scan/jobs').then(r => r.data);
export const getBatchJob         = (id)          => api.get(`/batch-scan/jobs/${id}`).then(r => r.data);
export const deleteBatchJob      = (id)          => api.delete(`/batch-scan/jobs/${id}`).then(r => r.data);
export const getBatchAggregate   = ()            => api.get('/batch-scan/aggregate').then(r => r.data);


// Image URLs
export const originalImageUrl = (id, token) => `${BASE}/scans/${id}/image/original?token=${token}`;
export const blurredImageUrl  = (id, token) => `${BASE}/scans/${id}/image/blurred?token=${token}`;

export default api;
