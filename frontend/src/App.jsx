import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import ScanPage from './pages/ScanPage';
import BlurPage from './pages/BlurPage';
import ReportPage from './pages/ReportPage';
import RecommendationsPage from './pages/RecommendationsPage';
import LoginPage from './pages/Login';
import RegisterPage from './pages/Register';
import ForgotPasswordPage from './pages/ForgotPassword';
import URLScanPage from './pages/URLScanPage';
import CloudScanPage from './pages/CloudScanPage';
import MonitorPage from './pages/MonitorPage';
import SocialScanPage from './pages/SocialScanPage';
import MetadataScanPage from './pages/MetadataScanPage';
import AttackSimulationPage from './pages/AttackSimulationPage';
import ScoreHistoryPage from './pages/ScoreHistoryPage';
import BatchScanPage from './pages/BatchScanPage';
import BackgroundAgentPage from './pages/BackgroundAgentPage';
import RemediationPage from './pages/RemediationPage';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const ProtectedLayout = ({ children, title }) => {
  const { isAuth } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  if (!isAuth) return <Navigate to="/login" replace />;

  return (
    <>
      {/* Sidebar */}
      <Sidebar collapsed={collapsed} />

      {/* Floating toggle tab — always visible on sidebar edge */}
      <button
        className={`sidebar-toggle-tab ${collapsed ? 'collapsed-tab' : ''}`}
        onClick={() => setCollapsed(c => !c)}
        title={collapsed ? 'Open sidebar' : 'Collapse sidebar'}
        aria-label={collapsed ? 'Open sidebar' : 'Collapse sidebar'}
      >
        {collapsed
          ? <ChevronRight size={13} strokeWidth={2.5} />
          : <ChevronLeft size={13} strokeWidth={2.5} />
        }
      </button>

      {/* Main content — clicking it collapses the sidebar */}
      <div
        className="main-area"
        onClick={() => { if (!collapsed) setCollapsed(true); }}
        style={{ cursor: collapsed ? 'default' : 'default' }}
      >
        <div className="top-bar" onClick={e => e.stopPropagation()}>
          <div className="top-bar-title">{title}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 6px var(--success)' }} />
            Backend Connected
          </div>
        </div>
        {/* page-content stops propagation so clicks on cards/inputs don't re-collapse */}
        <div className="page-content" onClick={e => e.stopPropagation()}>
          {children}
        </div>
      </div>
    </>
  );
};

const AppRoutes = () => {
  const { isAuth } = useAuth();
  return (
    <Routes>
      <Route path="/login"           element={isAuth ? <Navigate to="/dashboard" /> : <LoginPage />} />
      <Route path="/register"         element={isAuth ? <Navigate to="/dashboard" /> : <RegisterPage />} />
      <Route path="/forgot-password"  element={isAuth ? <Navigate to="/dashboard" /> : <ForgotPasswordPage />} />
      <Route path="/dashboard"       element={<ProtectedLayout title="Overview Dashboard"><Dashboard /></ProtectedLayout>} />
      <Route path="/scan"            element={<ProtectedLayout title="Upload & Scan"><ScanPage /></ProtectedLayout>} />
      <Route path="/blur"            element={<ProtectedLayout title="Blur Engine"><BlurPage /></ProtectedLayout>} />
      <Route path="/report"          element={<ProtectedLayout title="Report Generator"><ReportPage /></ProtectedLayout>} />
      <Route path="/recommendations" element={<ProtectedLayout title="Security Recommendations"><RecommendationsPage /></ProtectedLayout>} />
      <Route path="/url-scan"        element={<ProtectedLayout title="URL Scanner"><URLScanPage /></ProtectedLayout>} />
      <Route path="/cloud-scan"      element={<ProtectedLayout title="Cloud Scanner"><CloudScanPage /></ProtectedLayout>} />
      <Route path="/monitor"          element={<ProtectedLayout title="Screen Monitor"><MonitorPage /></ProtectedLayout>} />
      <Route path="/social-scan"      element={<ProtectedLayout title="Social Media Scanner"><SocialScanPage /></ProtectedLayout>} />
      <Route path="/metadata-scan"    element={<ProtectedLayout title="Metadata Scanner"><MetadataScanPage /></ProtectedLayout>} />
      <Route path="/attack-simulation" element={<ProtectedLayout title="Attack Simulation"><AttackSimulationPage /></ProtectedLayout>} />
      <Route path="/score-history"     element={<ProtectedLayout title="Score History"><ScoreHistoryPage /></ProtectedLayout>} />
      <Route path="/batch-scan"        element={<ProtectedLayout title="Batch Screenshot Scanner"><BatchScanPage /></ProtectedLayout>} />
      <Route path="/background-agent"  element={<ProtectedLayout title="Background Agent"><BackgroundAgentPage /></ProtectedLayout>} />
      <Route path="/remediation"        element={<ProtectedLayout title="Remediation Plan"><RemediationPage /></ProtectedLayout>} />
      <Route path="*" element={<Navigate to={isAuth ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
};

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
