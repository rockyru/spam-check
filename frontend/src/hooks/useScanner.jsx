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

  const analyze = async (inputType, content, file) => {
    if (cooldown > 0) return;
    setLoading(true);

    // --- MOCK LOGIC ---
    if (MOCK_MODE) {
      await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate 2s delay
      const randomResult = MOCK_RESULTS[Math.floor(Math.random() * MOCK_RESULTS.length)];
      setResult(randomResult);
      setLoading(false);
      triggerCooldown(10); // Shorter cooldown for testing
      return randomResult;
    }

    // --- REAL API LOGIC ---
    const formData = new FormData();
    formData.append('input_type', inputType);
    if (inputType === 'image') formData.append('file', file);
    else formData.append('text_content', content);

    try {
      const response = await fetch('http://localhost:8000/analyze', { method: 'POST', body: formData });
      const data = await response.json();

      if (JSON.stringify(data).includes("quota") || response.status === 429) {
        triggerCooldown(60);
        return { error: "QUOTA_EXCEEDED" };
      }

      setResult(data);
      triggerCooldown(30);
      return data;
    } catch (e) {
      return { error: "CONNECTION_FAILED" };
    } finally {
      setLoading(false);
    }
  };

  return { analyze, loading, result, cooldown, setResult };
};