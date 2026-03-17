import React, { useState, useRef, useEffect } from 'react';
import { useScanner } from '../hooks/useScanner';

const Scanner = ({ scannerRef }) => {
  const { analyze, loading, result, cooldown, sendFeedback, reset } = useScanner();

  const [content, setContent] = useState('');
  const [preview, setPreview] = useState(null);
  const [placeholder, setPlaceholder] = useState('Paste a sketchy link here...');
  const [lastType, setLastType] = useState('text'); 
  const [lastContent, setLastContent] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const fileInputRef = useRef(null);
  const resultRef = useRef(null);

  // Auto-scroll when result arrives
  useEffect(() => {
    if (result) {
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    }
  }, [result]);

  const handleLinkClick = () => {
    setPreview(null);
    setPlaceholder('https://...');
    setContent('https://');
    setTimeout(() => document.getElementById('magic-input')?.focus(), 10);
  };

  const handleImageUpload = (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result);
        setContent('');
        setLastType('image');
        setFeedbackSent(false);
        analyze('image', '', reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleVerify = () => {
    if (!content.trim() && !preview) return;
    let type = preview ? 'image' : (content.startsWith('http') ? 'url' : 'text');
    setLastType(type);
    setLastContent(content);
    setFeedbackSent(false);
    analyze(type, content, preview);
  };

  const handleClear = () => {
    setContent('');
    setPreview(null);
    setPlaceholder('Paste here...');
    reset()
  };

  const handleReportError = (userLabel) => {
    sendFeedback(lastType, lastContent || '', userLabel);
    setFeedbackSent(true);
  };

  return (
    <section ref={scannerRef} className="py-20 px-6 max-w-xl mx-auto min-h-screen">
      {/* HEADER SECTION */}
      <div className="mb-10 flex justify-between items-end animate-in fade-in slide-in-from-top-4 duration-700">
        <div>
          <h2 className="text-4xl font-black tracking-tight text-slate-900 mb-2">
            Stay <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-purple-600">Sharp.</span>
          </h2>
          <p className="text-slate-500 font-medium">Verify links, texts, or photos in seconds.</p>
           {/* Lightweight trust strip – hook it up to real stats later */}
           <p className="text-[14px] font-medium text-slate-400">
            Powered by security feeds and live scam reports from other users.
          </p>
        </div>
        {(content || preview) && (
          <button
            onClick={handleClear}
            className="group flex border p-2 rounded-[2em] cursor-pointer items-center gap-1 text-[10px] font-black uppercase text-rose-400 hover:text-rose-600 transition-all"
          >
            <span className="group-hover:rotate-90 transition-transform inline-block cursor-pointer">✕</span> Clear
          </button>
        )}
      </div>

      {/* THE MAGIC BOX */}
      <div
        className={`
        bg-white rounded-[3rem] p-5 border-2 transition-all duration-500 relative
        ${loading ? 'border-indigo-400 scale-[0.98] shadow-indigo-100' : 'border-slate-100 shadow-[0_20px_50px_rgba(0,0,0,0.04)]'}
        focus-within:border-indigo-300 focus-within:ring-8 focus-within:ring-indigo-50/50
      `}
      >
        <div className="p-4">
          {preview ? (
            <div className="relative group w-40 h-40 mx-auto rounded-[2rem] overflow-hidden border-4 border-slate-50 shadow-xl animate-in zoom-in duration-500">
              <img src={preview} alt="Preview" className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                 <button onClick={() => setPreview(null)} className="bg-white p-2 rounded-full shadow-lg cursor-pointer">✕</button>
              </div>
            </div>
          ) : (
            <textarea
              id="magic-input"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={placeholder}
              className="w-full bg-transparent border-none focus:ring-0 text-xl font-bold text-slate-800 placeholder:text-slate-200 min-h-[120px] resize-none"
            />
          )}
        </div>

        {/* Action Bar */}
        <div className="flex justify-between items-center p-2 bg-slate-50/80 backdrop-blur-md rounded-[2.5rem] border border-white">
          <div className="flex gap-3 pl-2">
            <button
              onClick={handleLinkClick}
              className="w-12 h-12 rounded-full bg-white flex items-center justify-center cursor-pointer shadow-sm hover:bg-amber-50 hover:scale-110 active:scale-95 transition-all border border-slate-100"
            >
              <span className="animate-bounce-subtle">🔗</span>
            </button>

            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-12 h-12 rounded-full bg-white flex items-center cursor-pointer justify-center shadow-sm hover:bg-indigo-50 hover:scale-110 active:scale-95 transition-all border border-slate-100"
            >
              <span>📷</span>
            </button>
            <input type="file" ref={fileInputRef} onChange={handleImageUpload} accept="image/*" className="hidden" />
          </div>

          <button
            onClick={handleVerify}
            disabled={loading || cooldown > 0 || (!content && !preview)}
            className={`
              relative overflow-hidden cursor-pointer px-10 py-4 rounded-full font-black text-xs uppercase tracking-widest transition-all active:scale-95 disabled:opacity-30
              ${loading ? 'bg-indigo-600 text-white' : 'bg-black text-white hover:bg-indigo-600 hover:shadow-[0_0_20px_rgba(79,70,229,0.4)]'}
            `}
          >
            {loading ? (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analyzing...
              </div>
            ) : cooldown > 0 ? `Wait ${cooldown}s` : 'Verify Now'}
          </button>
        </div>
      </div>

      {/* RESULTS SECTION */}
      {result && (
        <div 
          ref={resultRef}
          className={`
            mt-12 bg-white rounded-[3rem] p-10 shadow-2xl transition-all duration-700 animate-in fade-in slide-in-from-bottom-8
            border-t-8 ${
              Number(result.score) <= 3 ? 'border-emerald-400 shadow-emerald-100' : 
              Number(result.score) <= 7 ? 'border-amber-400 shadow-amber-100' : 'border-rose-400 shadow-rose-100'
            }
          `}
        >
          <div className="flex flex-col items-center gap-8">
            <div className="text-center">
              <div className="inline-flex items-baseline gap-1 mb-2">
                <span className="text-6xl font-black tracking-tighter text-slate-900 tabular-nums">
                  {Number(result.score)}
                </span>
                <span className="text-xl font-bold text-slate-300">/10</span>
              </div>
              <p className={`text-[10px] font-black uppercase tracking-[0.3em] px-6 py-2 rounded-full border ${
                Number(result.score) <= 3 ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 
                Number(result.score) <= 7 ? 'bg-amber-50 text-amber-600 border-amber-100' : 'bg-rose-50 text-rose-600 border-rose-100'
              }`}>
                {Number(result.score) <= 3 ? 'Verified Safe' : Number(result.score) <= 7 ? '⚠️ Be Careful' : '🚫 Scam Alert'}
              </p>
            </div>

            {/* GAUGE */}
            <div className="w-full px-4">
              <div className="relative mb-3 h-6">
                 <span 
                   className="absolute bottom-0 -translate-x-1/2 text-[10px] font-black uppercase text-slate-400 transition-all duration-[1500ms] ease-out whitespace-nowrap"
                   style={{ left: `${(Number(result.score) / 10) * 100}%` }}
                 >
                   {Number(result.score) <= 3 ? 'Solid' : Number(result.score) <= 7 ? 'Suspicious' : 'Dangerous'}
                 </span>
              </div>
              <div className="w-full h-4 bg-slate-100 rounded-full relative overflow-hidden p-1">
                <div
                  className={`h-full rounded-full transition-all duration-[1500ms] ease-out ${
                    Number(result.score) <= 3 ? 'bg-emerald-400' : 
                    Number(result.score) <= 7 ? 'bg-amber-400' : 'bg-rose-400'
                  }`}
                  style={{ width: `${(Number(result.score) / 10) * 100}%` }}
                />
              </div>
            </div>

            <div className="text-center max-w-sm">
              <h3 className="text-2xl font-bold text-slate-800 mb-4 leading-tight">
                {result.summary}
              </h3>
              <div className="flex flex-wrap justify-center gap-2">
                {result.flags?.map((flag, i) => (
                  <span key={i} className="px-4 py-1.5 bg-slate-50 text-[9px] font-black text-slate-500 rounded-lg border border-slate-100 uppercase tracking-widest">
                    #{flag.replace(/_/g, '')}
                  </span>
                ))}
              </div>
            </div>

            {/* Feedback System */}
            <div className="w-full pt-10 border-t border-slate-50 flex flex-col items-center gap-6">
              {!feedbackSent ? (
                <>
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-black">Was this accurate?</p>
                  <div className="flex flex-wrap justify-center gap-3">
                    <button onClick={() => handleReportError('safe')} className="px-6 py-3 cursor-pointer rounded-2xl border-2 border-emerald-200 text-[10px] font-black uppercase text-black hover:border-emerald-200 hover:text-emerald-500 transition-all active:scale-90">Yes, it's safe</button>
                    <button onClick={() => handleReportError('phishing')} className="px-6 py-3 cursor-pointer rounded-2xl border-2 border-rose-200 text-[10px] font-black uppercase text-black hover:border-rose-200 hover:text-rose-500 transition-all active:scale-90">No, it's a scam</button>
                  </div>
                </>
              ) : (
                <div className="flex items-center gap-2 text-emerald-500 animate-bounce">
                 
                  <p className="text-[10px] font-black uppercase tracking-widest">You're making the web safer!</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default Scanner;