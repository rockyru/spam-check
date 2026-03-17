import { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL;
const MOCK_MODE = false;

const MOCK_RESULTS = [
  { score: 1, summary: 'Everything looks good!', flags: ['OFFICIAL_SOURCE', 'SECURE_LINK'] },
  { score: 9, summary: 'Watch out! This looks like phishing.', flags: ['MALICIOUS', 'FAKE_SENDER'] },
];

export const useScanner = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [cooldown, setCooldown] = useState(() => {
    if (typeof window === 'undefined') return 0;
    const saved = localStorage.getItem('l7_cooldown_expiry');
    if (!saved) return 0;
    const remaining = Math.ceil((parseInt(saved) - Date.now()) / 1000);
    return remaining > 0 ? remaining : 0;
  });

  useEffect(() => {
    if (cooldown > 0) {
      const timer = setInterval(() => {
        setCooldown((prev) => {
          if (prev <= 1) {
            localStorage.removeItem('l7_cooldown_expiry');
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [cooldown]);

  const triggerCooldown = (seconds) => {
    const expiry = Date.now() + seconds * 1000;
    localStorage.setItem('l7_cooldown_expiry', expiry.toString());
    setCooldown(seconds);
  };

  const analyze = async (type, content, image) => {
    if (MOCK_MODE) {
      const mock = MOCK_RESULTS[Math.floor(Math.random() * MOCK_RESULTS.length)];
      setResult(mock);
      return;
    }

    if (!API_URL) {
      console.error('VITE_API_URL is not set');
      setResult({
        score: 0,
        summary: 'Configuration error: API URL not set',
        flags: ['ERROR'],
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, content, image }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
      // triggerCooldown(3);
    } catch (error) {
      console.error('Scan failed', error);
      setResult({
        score: 0,
        summary: 'Error checking this content',
        flags: ['ERROR'],
      });
    } finally {
      setLoading(false);
    }
  };

  const sendFeedback = async (inputType, rawContent, userLabel) => {
    if (MOCK_MODE) return;
    if (!API_URL || !result) return;

    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_type: inputType,
          raw_content: rawContent,
          predicted_score: result.score ?? 0,
          predicted_flags: result.flags ?? [],
          user_label: userLabel,
        }),
      });
    } catch (e) {
      console.error('Feedback failed', e);
    }
  };

  return { analyze, loading, result, cooldown, setResult, sendFeedback };
};
