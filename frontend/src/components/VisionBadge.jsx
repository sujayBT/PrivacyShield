import React from 'react';
import { Eye, User, CreditCard, PenLine, QrCode, FileType2 } from 'lucide-react';

/**
 * VisionBadge — shows Phase 6 vision detection summary bar.
 *
 * Props:
 *   docType:      string  e.g. "aadhaar_card"
 *   faceCount:    number
 *   isIdDoc:      bool
 *   compact:      bool    — one-line pill mode for table rows
 */

const DOC_LABELS = {
  aadhaar_card:    { label: 'Aadhaar Card',     color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.3)'   },
  pan_card:        { label: 'PAN Card',          color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.3)'   },
  passport:        { label: 'Passport',           color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.3)'   },
  driving_license: { label: 'Driving License',   color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)'  },
  bank_statement:  { label: 'Bank Statement',    color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)'  },
  medical_record:  { label: 'Medical Record',    color: '#a855f7', bg: 'rgba(168,85,247,0.1)',  border: 'rgba(168,85,247,0.3)'  },
  tax_document:    { label: 'Tax Document',      color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)'  },
  insurance:       { label: 'Insurance Doc',     color: '#6366f1', bg: 'rgba(99,102,241,0.1)',  border: 'rgba(99,102,241,0.3)'  },
  screenshot:      { label: 'Screenshot',        color: '#64748b', bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.3)' },
  unknown:         { label: 'Unknown',           color: '#64748b', bg: 'rgba(100,116,139,0.07)',border: 'rgba(100,116,139,0.2)' },
};

const VisionBadge = ({ docType, faceCount = 0, isIdDoc = false, compact = false }) => {
  const hasAny = (docType && docType !== 'unknown') || faceCount > 0 || isIdDoc;
  if (!hasAny) return null;

  const doc  = DOC_LABELS[docType] || DOC_LABELS.unknown;
  const label = doc.label;

  if (compact) {
    return (
      <span
        title={`Vision AI: ${label}${faceCount > 0 ? `, ${faceCount} face(s)` : ''}${isIdDoc ? ' · ID Doc' : ''}`}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 10, fontWeight: 700, letterSpacing: '0.02em',
          color: doc.color, background: doc.bg,
          border: `1px solid ${doc.border}`,
          borderRadius: 5, padding: '1px 6px', lineHeight: 1.4, flexShrink: 0,
        }}
      >
        <Eye size={9} />
        {isIdDoc ? '🪪' : '📄'} {label}
        {faceCount > 0 && <span style={{ color: '#ef4444' }}>· 👤×{faceCount}</span>}
      </span>
    );
  }

  return (
    <div style={{
      borderRadius: 10, overflow: 'hidden',
      border: `1px solid ${isIdDoc ? 'rgba(239,68,68,0.3)' : 'rgba(100,116,139,0.2)'}`,
      background: 'var(--bg-card)',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 14px',
        background: isIdDoc ? 'rgba(239,68,68,0.06)' : 'rgba(0,0,0,0.02)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <Eye size={13} color={isIdDoc ? '#ef4444' : 'var(--accent)'} />
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
          Vision AI Analysis
        </span>
        <span style={{
          marginLeft: 'auto', fontSize: 10, fontWeight: 700,
          color: '#22c55e', background: 'rgba(34,197,94,0.08)',
          border: '1px solid rgba(34,197,94,0.2)',
          borderRadius: 4, padding: '1px 6px',
        }}>
          OpenCV 4
        </span>
      </div>

      {/* Pills row */}
      <div style={{ padding: '10px 14px', display: 'flex', flexWrap: 'wrap', gap: 7 }}>

        {/* Document type */}
        {docType && docType !== 'unknown' && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            fontSize: 11, fontWeight: 600,
            color: doc.color, background: doc.bg,
            border: `1px solid ${doc.border}`,
            borderRadius: 6, padding: '4px 10px',
          }}>
            <FileType2 size={12} />
            {label}
          </span>
        )}

        {/* ID document alert */}
        {isIdDoc && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            fontSize: 11, fontWeight: 700,
            color: '#ef4444', background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 6, padding: '4px 10px',
          }}>
            <CreditCard size={12} />
            ID Document Detected
          </span>
        )}

        {/* Face count */}
        {faceCount > 0 && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            fontSize: 11, fontWeight: 700,
            color: '#ef4444', background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.25)',
            borderRadius: 6, padding: '4px 10px',
          }}>
            <User size={12} />
            {faceCount} Face{faceCount > 1 ? 's' : ''} Detected
          </span>
        )}
      </div>
    </div>
  );
};

export default VisionBadge;
