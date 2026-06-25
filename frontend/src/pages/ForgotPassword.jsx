import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, AlertCircle, CheckCircle, ArrowLeft, User, KeyRound, ShieldCheck, Lock } from 'lucide-react';
import { changePassword } from '../api';

// ── Validation helpers ────────────────────────────────────────────────────────
const rules = {
  username:    v => !v.trim() ? 'Username is required.' : v.trim().length < 3 ? 'Username must be at least 3 characters.' : '',
  newPassword: v => !v ? 'New password is required.' : v.length < 6 ? 'New password must be at least 6 characters.' : '',
  confirm:     (v, np) => !v ? 'Please confirm your new password.' : v !== np ? 'Passwords do not match.' : '',
};

export default function ForgotPasswordPage() {
  const navigate  = useNavigate();
  const [form, setForm]       = useState({ username: '', newPassword: '', confirm: '' });
  const [showNew, setShowNew] = useState(false);
  const [showCnf, setShowCnf] = useState(false);
  const [touched, setTouched] = useState({});
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState('');
  const [success, setSuccess]         = useState(false);

  const errs = {
    username:    rules.username(form.username),
    newPassword: rules.newPassword(form.newPassword),
    confirm:     rules.confirm(form.confirm, form.newPassword),
  };
  const formValid = Object.values(errs).every(e => !e);

  const set = (field) => (e) => {
    setForm(f => ({ ...f, [field]: e.target.value }));
    setServerError('');
  };
  const blur = (field) => () => setTouched(t => ({ ...t, [field]: true }));

  const handle = async (e) => {
    e.preventDefault();
    setTouched({ username: true, newPassword: true, confirm: true });
    if (!formValid) return;
    setLoading(true);
    setServerError('');
    try {
      await changePassword(form.username.trim(), '', form.newPassword);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Something went wrong. Please try again.';
      setServerError(msg);
    } finally {
      setLoading(false);
    }
  };

  // ── Mouse tracking for gradient ─────────────────────────────────────────────
  const [mousePos, setMousePos] = React.useState({ x: '50%', y: '50%' });
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setMousePos({ x: `${x}%`, y: `${y}%` });
  };

  // ── Success screen ──────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="auth-page" style={{
        background: `radial-gradient(circle 500px at ${mousePos.x} ${mousePos.y}, rgba(32,101,209,0.08) 0%, #f5f7fa 100%)`
      }}>
        <div className="auth-left">
          <div className="auth-card animate-up" style={{ textAlign: 'center' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'rgba(34,197,94,0.15)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CheckCircle size={32} color="#22c55e" />
              </div>
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 8 }}>
              Password Updated!
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
              Your password has been changed successfully.<br />
              Redirecting you to the sign in page…
            </p>
            <div className="spinner" style={{ margin: '0 auto', borderColor: 'rgba(34,197,94,0.3)', borderTopColor: '#22c55e' }} />
          </div>
        </div>

        {/* Right panel */}
        <div className="auth-right">
          <ResetPanel />
        </div>
      </div>
    );
  }

  // ── Main form ───────────────────────────────────────────────────────────────
  return (
    <div className="auth-page" onMouseMove={handleMouseMove} style={{
      background: `radial-gradient(circle 500px at ${mousePos.x} ${mousePos.y}, rgba(32,101,209,0.08) 0%, #f5f7fa 100%)`
    }}>

      {/* ── LEFT: Form card ── */}
      <div className="auth-left">
        <div className="auth-card animate-up">

          {/* Header */}
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
              <div style={{ width: 64, height: 64, borderRadius: 18,
                            background: 'linear-gradient(135deg, #1e3a8a22, #3b82f622)',
                            border: '1.5px solid rgba(59,130,246,0.3)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <KeyRound size={28} color="var(--accent)" />
              </div>
            </div>
            <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4, color: 'var(--text-primary)' }}>
              Reset Password
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Enter your username and choose a new password
            </p>
          </div>

          {/* Server error */}
          {serverError && (
            <div className="alert alert-error" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              {serverError}
            </div>
          )}

          <form onSubmit={handle} autoComplete="off" noValidate
                style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

            {/* Username */}
            <div>
              <label style={labelStyle}>Username</label>
              <div style={{ position: 'relative' }}>
                <span style={iconWrap}><User size={15} /></span>
                <input className="input" type="text"
                  value={form.username} onChange={set('username')} onBlur={blur('username')}
                  placeholder="Your account username"
                  autoComplete="off" name="fp-username"
                  style={{ ...fieldBox(touched.username && errs.username), paddingLeft: 38 }}
                />
              </div>
              {touched.username && errs.username &&
                <p style={errStyle}><AlertCircle size={12} /> {errs.username}</p>}
            </div>


            {/* New password */}
            <div>
              <label style={labelStyle}>New Password</label>
              <div className="input-wrapper" style={{ position: 'relative' }}>
                <span style={iconWrap}><KeyRound size={15} /></span>
                <input className="input" type={showNew ? 'text' : 'password'}
                  value={form.newPassword} onChange={set('newPassword')} onBlur={blur('newPassword')}
                  placeholder="Min. 6 characters"
                  autoComplete="new-password" name="fp-newpass"
                  style={{ ...fieldBox(touched.newPassword && errs.newPassword), paddingLeft: 38 }}
                />
                <button type="button" className="input-eye" onClick={() => setShowNew(s => !s)}
                        style={{ color: showNew ? 'var(--accent)' : undefined }}>
                  {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {touched.newPassword && errs.newPassword &&
                <p style={errStyle}><AlertCircle size={12} /> {errs.newPassword}</p>}
            </div>

            {/* Confirm new password */}
            <div>
              <label style={labelStyle}>Confirm New Password</label>
              <div className="input-wrapper" style={{ position: 'relative' }}>
                <span style={iconWrap}><KeyRound size={15} /></span>
                <input className="input" type={showCnf ? 'text' : 'password'}
                  value={form.confirm} onChange={set('confirm')} onBlur={blur('confirm')}
                  placeholder="Re-enter new password"
                  autoComplete="new-password" name="fp-confirm"
                  style={{ ...fieldBox(touched.confirm && errs.confirm), paddingLeft: 38 }}
                />
                <button type="button" className="input-eye" onClick={() => setShowCnf(s => !s)}
                        style={{ color: showCnf ? 'var(--accent)' : undefined }}>
                  {showCnf ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {touched.confirm && errs.confirm &&
                <p style={errStyle}><AlertCircle size={12} /> {errs.confirm}</p>}
              {/* Live match indicator */}
              {form.confirm && form.newPassword && !errs.confirm && (
                <p style={{ ...errStyle, color: '#22c55e' }}>
                  <CheckCircle size={12} /> Passwords match
                </p>
              )}
            </div>

            {/* Submit */}
            <button type="submit" className="btn btn-primary btn-lg"
              disabled={loading}
              style={{ width: '100%', marginTop: 4,
                       background: 'linear-gradient(135deg, #2065d1, #1757c2)',
                       opacity: loading ? 0.75 : 1 }}>
              {loading
                ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} /> Updating...</>
                : 'Update Password'}
            </button>
          </form>

          {/* Back to login */}
          <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
            <Link to="/login"
              style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'none',
                       display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <ArrowLeft size={13} /> Back to Sign In
            </Link>
          </p>
        </div>{/* /auth-card */}
      </div>{/* /auth-left */}

      {/* ── RIGHT: Security illustration panel ── */}
      <div className="auth-right">
        <ResetPanel />
      </div>

    </div>
  );
}

// ── Reset Panel (right side illustration) ────────────────────────────────────
function ResetPanel() {
  const tips = [
    { icon: '🔒', text: 'Use at least 8 characters' },
    { icon: '🔡', text: 'Mix letters, numbers & symbols' },
    { icon: '🚫', text: 'Avoid reusing old passwords' },
  ];

  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '48px 40px', gap: 28, textAlign: 'center',
      backgroundColor: 'transparent',
    }}>
      <div style={{
        maxWidth: 440,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 22,
      }}>
        {/* Illustration image */}
        <img
          src="/forgot_password_panel.png"
          alt="Secure Password Reset"
          style={{
            width: '100%',
            maxWidth: 320,
            height: 'auto',
            borderRadius: 20,
            boxShadow: '0 12px 48px rgba(32,101,209,0.18)',
            transition: 'transform 0.6s cubic-bezier(0.16,1,0.3,1)',
          }}
          onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-6px) scale(1.025)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0) scale(1)'}
        />

        {/* Heading + subtitle */}
        <div>
          <h2 style={{
            fontSize: 26, fontWeight: 800,
            color: '#0f172a', marginBottom: 12, lineHeight: 1.3,
          }}>
            Secure Your Account
          </h2>
          <p style={{
            fontSize: 14, color: '#475569',
            lineHeight: 1.6, maxWidth: 360, margin: '0 auto',
          }}>
            Choose a strong new password to keep your privacy dashboard protected.
            Your security is our top priority.
          </p>
        </div>

        {/* Password tips */}
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 10,
          width: '100%', maxWidth: 340,
        }}>
          {tips.map((tip, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              background: 'rgba(32,101,209,0.06)',
              border: '1px solid rgba(32,101,209,0.12)',
              borderRadius: 10, padding: '10px 14px',
              fontSize: 13, color: '#334155', fontWeight: 500,
            }}>
              <span style={{ fontSize: 18 }}>{tip.icon}</span>
              {tip.text}
            </div>
          ))}
        </div>
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
const iconWrap = {
  position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)',
  color: 'var(--text-secondary)', pointerEvents: 'none', zIndex: 1,
  display: 'flex', alignItems: 'center',
};
const fieldBox = (hasErr) => ({
  border: hasErr ? '1.5px solid #ef4444' : '1.5px solid var(--border)',
  borderRadius: 10,
  background: 'var(--input-bg, rgba(255,255,255,0.05))',
  transition: 'border-color 0.2s',
});
