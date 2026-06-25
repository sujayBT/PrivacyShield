import { useState, useEffect, useRef } from 'react';
import { getBaseUrl } from '../api';

/**
 * Fetches an authenticated image from the FastAPI backend and
 * returns a local blob objectURL safe for use in <img src=...>
 * Automatically revokes the URL on cleanup / re-fetch.
 */
export const useAuthImage = (scanId, type) => {
  const [src, setSrc] = useState(null);
  const urlRef = useRef(null);

  useEffect(() => {
    if (!scanId || !type) { setSrc(null); return; }

    let cancelled = false;
    const token = localStorage.getItem('token');

    fetch(`${getBaseUrl()}/scans/${scanId}/image/${type}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => {
        if (!r.ok) throw new Error('Image not available');
        return r.blob();
      })
      .then(blob => {
        if (cancelled) return;
        if (urlRef.current) URL.revokeObjectURL(urlRef.current);
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        setSrc(url);
      })
      .catch(() => { if (!cancelled) setSrc(null); });

    return () => {
      cancelled = true;
      if (urlRef.current) { URL.revokeObjectURL(urlRef.current); urlRef.current = null; }
    };
  }, [scanId, type]);

  return src;
};
