import { useState, useEffect } from 'react';

// TOGGLE THIS TO TRUE TO SAVE YOUR QUOTA
const MOCK_MODE = true; 

const MOCK_RESULTS = [
  { 
    score: 1, 
    summary: "Everything looks good! This link leads to the official site and shows no signs of a scam.", 
    flags: ["OFFICIAL_SOURCE", "SECURE_LINK"] 
  },
  { 
    score: 9, 
    summary: "Watch out! This looks like a phishing attempt designed to steal your login info.", 
    flags: ["MALICIOUS", "FAKE_SENDER"] 
  }
];

export const useScanner = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [cooldown, setCooldown] = useState(() => {
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

  const analyze = async (type, content) => {
  setLoading(true);
  try {
    const response = await fetch('http://localhost:8000/api/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, content })
    });
    const data = await response.json();
    setResult(data);
  } catch (error) {
    console.error("Scan failed", error);
  } finally {
    setLoading(false);
  }
};

  return { analyze, loading, result, cooldown, setResult };
};