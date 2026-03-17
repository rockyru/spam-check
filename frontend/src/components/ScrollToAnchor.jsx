// ScrollToAnchor.jsx
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

function ScrollToAnchor() {
  const { hash } = useLocation();

  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(hash.slice(1));
    if (!el) return;
    setTimeout(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }, [hash]);

  return null;
}

export default ScrollToAnchor;
