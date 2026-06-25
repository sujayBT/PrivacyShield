import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react';

export default function RegisterPage() {
  const [username, setUsername]     = useState('');
  const [password, setPassword]     = useState('');
  const [confirm,  setConfirm]      = useState('');
  const [showPass, setShowPass]     = useState(false);
  const [showConf, setShowConf]     = useState(false);
  const [error,    setError]        = useState('');
  const { doRegister, loading } = useAuth();
  const navigate = useNavigate();

  // Interactive background coordinate state
  const [mousePos, setMousePos] = useState({ x: '50%', y: '50%' });
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setMousePos({ x: `${x}%`, y: `${y}%` });
  };

  // Live match state — only show indicator when user has started typing confirm
  const confirmTouched = confirm.length > 0;
  const passwordsMatch = password === confirm;

  const handle = async (e) => {
    e.preventDefault(); setError('');
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (!passwordsMatch) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }
    try {
      await doRegister(username, password);
      navigate('/login?registered=1');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Username may already be taken.');
    }
  };

  const LABEL_STYLE = {
    display: 'block', fontSize: 12, fontWeight: 600,
    color: 'var(--text-secondary)', marginBottom: 6,
    textTransform: 'uppercase', letterSpacing: '0.06em',
  };

  return (
    <div className="auth-page" onMouseMove={handleMouseMove} style={{
      background: `radial-gradient(circle 500px at ${mousePos.x} ${mousePos.y}, rgba(32, 101, 209, 0.08) 0%, #f5f7fa 100%)`
    }}>
      <div className="auth-left">
        <div className="auth-card animate-up">
        {/* Icon */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ width: 60, height: 60, background: 'linear-gradient(135deg, #2065d1, #7c3aed)', borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontSize: 30, boxShadow: '0 0 24px rgba(32,101,209,0.35)' }}>🔐</div>
          <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4, color: 'var(--text-primary)' }}>Create Account</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Start protecting your digital footprint</p>
        </div>

        {error && (
          <div className="alert alert-error">{error}</div>
        )}

        <form onSubmit={handle} style={{ display: 'flex', flexDirection: 'column', gap: 16 }} autoComplete="off">

          {/* Username */}
          <div>
            <label style={LABEL_STYLE}>Username</label>
            <input
              className="input" type="text"
              value={username} onChange={e => setUsername(e.target.value)}
              placeholder="Choose a username" required autoFocus
              autoComplete="off"
            />
          </div>

          {/* Password */}
          <div>
            <label style={LABEL_STYLE}>Password</label>
            <div className="input-wrapper">
              <input
                className="input" type={showPass ? 'text' : 'password'}
                value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Create a strong password" required
                autoComplete="new-password"
              />
              <button type="button" className="input-eye" onClick={() => setShowPass(s => !s)}>
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 5 }}>Minimum 6 characters</div>
          </div>

          {/* Confirm Password */}
          <div>
            <label style={LABEL_STYLE}>Confirm Password</label>
            <div className="input-wrapper">
              <input
                className="input"
                type={showConf ? 'text' : 'password'}
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="Re-enter your password"
                required
                autoComplete="new-password"
                style={{
                  borderColor: confirmTouched
                    ? (passwordsMatch ? 'var(--accent)' : '#ef4444')
                    : undefined,
                  boxShadow: confirmTouched
                    ? (passwordsMatch ? '0 0 0 2px rgba(32,101,209,0.18)' : '0 0 0 2px rgba(239,68,68,0.18)')
                    : undefined,
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                }}
              />
              <button type="button" className="input-eye" onClick={() => setShowConf(s => !s)}>
                {showConf ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Live match indicator */}
            {confirmTouched && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 5,
                marginTop: 6, fontSize: 12, fontWeight: 500,
                color: passwordsMatch ? '#22c55e' : '#ef4444',
                transition: 'color 0.2s',
              }}>
                {passwordsMatch
                  ? <><CheckCircle size={13} /> Passwords match</>
                  : <><XCircle size={13} /> Passwords do not match</>
                }
              </div>
            )}
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            style={{ width: '100%', marginTop: 4, opacity: (confirmTouched && !passwordsMatch) ? 0.6 : 1, transition: 'opacity 0.2s' }}
            disabled={loading || (confirmTouched && !passwordsMatch)}
          >
            {loading
              ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Creating account...</>
              : 'Create Account'
            }
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: 'var(--accent)', fontWeight: 600 }}>Sign In</Link>
        </p>
        </div>{/* /auth-card */}
      </div>{/* /auth-left */}
      <div className="auth-right">
        <RegisterPanel />
      </div>
    </div>
  );
}

// ── Register page right panel ─────────────────────────────────────────────────
function RegisterPanel() {
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
            One Account. Total Protection.
          </h2>
          <p style={{ 
            fontSize: 14, 
            color: '#475569', 
            lineHeight: 1.6,
            maxWidth: 380,
            margin: '0 auto'
          }}>
            Create your account to start scanning local files, external links, cloud documents, and social media for sensitive data exposure.
          </p>
        </div>
      </div>
    </div>
  );
}
