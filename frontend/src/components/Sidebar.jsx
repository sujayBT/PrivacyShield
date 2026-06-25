import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import {
  LayoutDashboard, ScanSearch, EyeOff,
  FileBarChart2, ShieldCheck, Globe, Cloud, MonitorCheck, Users, FileSearch2, Zap, Activity, Layers, LogOut, Moon, Sun, Shield, Wrench
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/dashboard',          icon: LayoutDashboard, label: 'Overview',                  color: '#4ade80' },
  { to: '/scan',               icon: ScanSearch,      label: 'Upload & Scan',              color: '#60a5fa' },
  { to: '/blur',               icon: EyeOff,          label: 'Blur Engine',                color: '#a78bfa' },
  { to: '/metadata-scan',      icon: FileSearch2,     label: 'Metadata Scanner',           color: '#fb923c' },
  { to: '/attack-simulation',  icon: Zap,             label: 'Attack Simulation',          color: '#dc2626' },
  { to: '/batch-scan',         icon: Layers,          label: 'Batch Screenshot Scanner',   color: '#a855f7' },
  { to: '/url-scan',           icon: Globe,           label: 'URL Scanner',                color: '#22d3ee' },
  { to: '/cloud-scan',         icon: Cloud,           label: 'Cloud Scanner',              color: '#38bdf8' },
  { to: '/monitor',            icon: MonitorCheck,    label: 'Screen Monitor',             color: '#f87171' },
  { to: '/social-scan',        icon: Users,           label: 'Social Scanner',             color: '#c084fc' },
  { to: '/score-history',      icon: Activity,        label: 'Score History',              color: '#60a5fa' },
  { to: '/background-agent',   icon: Shield,          label: 'Background Agent',           color: '#22c55e' },
  { to: '/report',             icon: FileBarChart2,   label: 'Report Generator',           color: '#34d399' },
  { to: '/recommendations',    icon: ShieldCheck,     label: 'Recommendations',            color: '#fbbf24' },
  { to: '/remediation',        icon: Wrench,          label: 'Remediation Plan',           color: '#f59e0b' },
];


// App logo — privacy eye with lock
const PrivacyLogo = () => (
  <img
    src="/app_logo.png"
    alt="PrivacyShield Logo"
    style={{ width: 38, height: 38, borderRadius: 10, objectFit: 'cover', flexShrink: 0 }}
  />
);

const Sidebar = ({ collapsed = false }) => {
  const { username, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      {/* Stop clicks inside sidebar from bubbling to main-area */}
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        onClick={e => e.stopPropagation()}>
      {/* Brand — no border bottom so it doesn't create a shared line with topbar */}
      <div className="sidebar-brand">
        <PrivacyLogo />
        <div className="sidebar-brand-text">
          Privacy Tool
          <span>Exposure Scanner</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, icon: Icon, label, color }) => (
          <NavLink
            key={to} to={to}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            {({ isActive }) => (
              <>
                <span className="nav-icon" style={{ color: isActive ? color : undefined }}>
                  <Icon size={21} strokeWidth={isActive ? 2.2 : 1.8} />
                </span>
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="dark-toggle">
          <span className="dark-toggle-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {isDark ? <Moon size={14} /> : <Sun size={14} />}
            {isDark ? 'Dark Mode' : 'Light Mode'}
          </span>
          <button
            className={`toggle-switch ${isDark ? 'on' : ''}`}
            onClick={toggle}
            aria-label="Toggle dark mode"
          />
        </div>

        <div className="user-pill" onClick={handleLogout} title="Click to logout">
          <div className="user-avatar">{username?.[0]?.toUpperCase() || 'U'}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--sidebar-user-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {username}
            </div>
            <div style={{ fontSize: 10, color: 'var(--sidebar-user-sub)' }}>Click to logout</div>
          </div>
          <LogOut size={14} style={{ color: 'var(--sidebar-text)', flexShrink: 0 }} />
        </div>
      </div>
      </div>
    </aside>
  );
};

export default Sidebar;
