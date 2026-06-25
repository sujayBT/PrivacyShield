import { useEffect } from 'react';
import ReactDOM from 'react-dom';

/**
 * Full-screen lightbox with ESC-to-close and click-outside-to-close.
 * Props:
 *   src    – image blob URL or any image src
 *   label  – caption shown at the bottom
 *   onClose – callback to close the lightbox
 */
export default function Lightbox({ src, label, onClose }) {
  // ESC key handler
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!src) return null;

  return ReactDOM.createPortal(
    <div className="lightbox-overlay" onClick={onClose}>
      <img
        src={src}
        alt={label || 'Image'}
        onClick={e => e.stopPropagation()} // Don't close when clicking the image
      />
      {label && <div className="lightbox-label">{label}</div>}
      <button className="lightbox-close" onClick={onClose} aria-label="Close">✕</button>
    </div>,
    document.body
  );
}
