import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, CheckCircle, AlertCircle, User, Lock } from 'lucide-react';

// ── Inline validation helpers ─────────────────────────────────────────────────
const validateUsername = (v) => {
  if (!v.trim()) return 'Username is required.';
  if (v.trim().length < 3) return 'Username must be at least 3 characters.';
  return '';
};
const validatePassword = (v) => {
  if (!v) return 'Password is required.';
  if (v.length < 6) return 'Password must be at least 6 characters.';
  return '';
};

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [touched, setTouched]   = useState({ username: false, password: false });
  const [serverError, setServerError] = useState('');
  const { doLogin, loading } = useAuth();
  const navigate = useNavigate();

  // Interactive background coordinate state
  const [mousePos, setMousePos] = useState({ x: '50%', y: '50%' });
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setMousePos({ x: `${x}%`, y: `${y}%` });
  };

  // Clear autofill on mount
  useEffect(() => { setUsername(''); setPassword(''); }, []);

  const justRegistered = new URLSearchParams(window.location.search).get('registered');

  // Per-field inline errors (only shown after user has touched the field)
  const usernameErr = touched.username ? validateUsername(username) : '';
  const passwordErr = touched.password ? validatePassword(password)  : '';
  const formValid   = !validateUsername(username) && !validatePassword(password);

  const handle = async (e) => {
    e.preventDefault();
    // Force-show all errors on submit attempt
    setTouched({ username: true, password: true });
    if (!formValid) return;
    setServerError('');
    try {
      await doLogin(username.trim(), password);
      navigate('/dashboard');
    } catch (err) {
      const msg = err?.response?.data?.detail || '';
      if (msg.toLowerCase().includes('incorrect') || msg.toLowerCase().includes('unauthorized')) {
        setServerError('Incorrect username or password. Please try again.');
      } else if (msg) {
        setServerError(msg);
      } else {
        setServerError('Something went wrong. Please try again.');
      }
    }
  };

  // Field styling helpers
  const fieldStyle = (hasErr) => ({
    border: hasErr ? '1.5px solid #ef4444' : '1.5px solid var(--border)',
    borderRadius: 10,
    background: 'var(--input-bg, rgba(255,255,255,0.05))',
    transition: 'border-color 0.2s',
  });

  return (
    <div className="auth-page" onMouseMove={handleMouseMove} style={{
      background: `radial-gradient(circle 500px at ${mousePos.x} ${mousePos.y}, rgba(32, 101, 209, 0.08) 0%, #f5f7fa 100%)`
    }}>

      {/* ── LEFT: Login card (unchanged) ── */}
      <div className="auth-left">
        <div className="auth-card animate-up">

        {/* Logo + heading */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
            <img
              src="/app_logo.png"
              alt="Privacy Tool"
              style={{ width: 72, height: 72, borderRadius: 20, objectFit: 'cover',
                       boxShadow: '0 0 32px rgba(0,180,255,0.35)' }}
            />
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4, color: 'var(--text-primary)' }}>
            Welcome back
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Sign in to your privacy dashboard
          </p>
        </div>

        {/* Success banner from registration */}
        {justRegistered && (
          <div className="alert alert-success" style={{ marginBottom: 16 }}>
            <CheckCircle size={16} /> Account created successfully! Please sign in.
          </div>
        )}

        {/* Server-side error */}
        {serverError && (
          <div className="alert alert-error" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            {serverError}
          </div>
        )}

        <form onSubmit={handle} autoComplete="off" noValidate
              style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

          {/* ── Username field ── */}
          <div>
            <label style={labelStyle}>Username</label>
            <div style={{ position: 'relative' }}>
              <span style={iconWrapStyle}><User size={15} /></span>
              <input
                className="input"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                onBlur={() => setTouched(t => ({ ...t, username: true }))}
                placeholder="Enter your username"
                autoComplete="off"
                name="username-login"
                style={{ ...fieldStyle(!!usernameErr), paddingLeft: 38 }}
              />
            </div>
            {usernameErr && <p style={errStyle}><AlertCircle size={12} /> {usernameErr}</p>}
          </div>

          {/* ── Password field ── */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label style={{ ...labelStyle, marginBottom: 0 }}>Password</label>
              <Link
                to="/forgot-password"
                style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600, textDecoration: 'none' }}
              >
                Forgot password?
              </Link>
            </div>
            <div className="input-wrapper" style={{ position: 'relative' }}>
              <span style={iconWrapStyle}><Lock size={15} /></span>
              <input
                className="input"
                type={showPass ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                onBlur={() => setTouched(t => ({ ...t, password: true }))}
                placeholder="Enter your password"
                autoComplete="new-password"
                name="password-login"
                style={{ ...fieldStyle(!!passwordErr), paddingLeft: 38 }}
              />
              <button type="button" className="input-eye" onClick={() => setShowPass(s => !s)}
                      style={{ color: showPass ? 'var(--accent)' : undefined }}>
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {passwordErr && <p style={errStyle}><AlertCircle size={12} /> {passwordErr}</p>}
          </div>

          {/* ── Submit ── */}
          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading}
            style={{ width: '100%', marginTop: 4, background: 'linear-gradient(135deg, #2065d1, #1757c2)',
                     opacity: loading ? 0.75 : 1 }}
          >
            {loading
              ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Signing in...</>
              : 'Sign In'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
          Don't have an account?{' '}
          <Link to="/register" style={{ color: 'var(--accent)', fontWeight: 600 }}>Create account</Link>
        </p>
        </div>{/* /auth-card */}
      </div>{/* /auth-left */}

      {/* ── RIGHT: Interactive Privacy Panel ── */}
      <div className="auth-right">
        <PrivacyPanel />
      </div>

    </div>
  );
}

// ── Shared micro-styles ───────────────────────────────────────────────────────
const labelStyle = {
  display: 'block', fontSize: 12, fontWeight: 600,
  color: 'var(--text-secondary)', marginBottom: 6,
  textTransform: 'uppercase', letterSpacing: '0.06em',
};
const errStyle = {
  display: 'flex', alignItems: 'center', gap: 4,
  fontSize: 11.5, color: '#ef4444', marginTop: 5, fontWeight: 500,
};
const iconWrapStyle = {
  position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)',
  color: 'var(--text-secondary)', pointerEvents: 'none', zIndex: 1,
  display: 'flex', alignItems: 'center',
};

// ── Simple Privacy Illustration Panel (right side) ───────────────────────────
function PrivacyPanel() {
  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '48px 40px', gap: 24, textAlign: 'center',
      backgroundColor: 'transparent'
    }}>
      <div style={{
        maxWidth: 440,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 20
      }}>
        <img 
          src="/privacy_vector.png" 
          alt="Privacy Protection" 
          style={{ 
            width: '100%', 
            maxWidth: 340, 
            height: 'auto',
            marginBottom: 10,
            borderRadius: 16
          }} 
        />
        <div>
          <h2 style={{ 
            fontSize: 26, 
            fontWeight: 800, 
            color: '#0f172a', 
            marginBottom: 12,
            lineHeight: 1.3
          }}>
            Protect Your Personal Data
          </h2>
          <p style={{ 
            fontSize: 14, 
            color: '#475569', 
            lineHeight: 1.6,
            maxWidth: 380,
            margin: '0 auto'
          }}>
            Instantly scan, detect, and remediate personal exposure (PII) across documents, images, cloud paths, and social profiles.
          </p>
        </div>
      </div>
    </div>
  );
}

