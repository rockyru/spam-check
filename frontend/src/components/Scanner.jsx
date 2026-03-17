import React, { useState, useRef } from 'react';
import { useScanner } from '../hooks/useScanner';


const Scanner = ({ scannerRef }) => {
  const { analyze, loading, result, cooldown } = useScanner();
  const [content, setContent] = useState('');
  const [preview, setPreview] = useState(null);
  const [placeholder, setPlaceholder] = useState("Paste here...");
  const fileInputRef = useRef(null);

  // 1. Handle Link Icon Click
  const handleLinkClick = () => {
    setPreview(null);
    setPlaceholder("https://...");
    setContent("https://");
    setTimeout(() => document.getElementById('magic-input')?.focus(), 10);
  };

  // 2. Handle Image Selection
  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result;
        setPreview(base64String);
        setContent('');
        // We pass the base64 string directly to our analyze hook
        analyze('auto', '', base64String);
      };
      reader.readAsDataURL(file);
    }
  };

  // 3. Trigger Analysis (Text or combined)
  const handleVerify = () => {
    // If there is a preview, we are analyzing an image. 
    // If not, we are analyzing the text content.
    analyze('auto', content, preview);
  };

  // 4. Clear State
  const handleClear = () => {
    setContent('');
    setPreview(null);
    setPlaceholder("Paste here...");
  };

  return (
    <section ref={scannerRef} className="py-12 px-6 max-w-xl mx-auto min-h-[700px]">
      
      {/* HEADER SECTION */}
      <div className="mb-8 flex justify-between items-end">
        <div>
           <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Check anything.</h2>
           <p className="text-slate-500 font-medium text-sm">Paste a link, a text, or a photo.</p>
        </div>
        {(content || preview) && (
           <button 
             onClick={handleClear} 
             className="text-[10px] font-black uppercase text-rose-400 hover:text-rose-600 transition-colors"
           >
             Clear
           </button>
        )}
      </div>

      {/* THE MAGIC BOX */}
      <div className={`
        bg-white rounded-[2.5rem] p-4 border-2 transition-all duration-500
        ${!content && !preview && !loading ? 'animate-soft-pulse' : 'border-slate-100'}
        focus-within:border-[#D6D3F9] focus-within:ring-4 focus-within:ring-[#D6D3F9]/10 focus-within:animate-none
        shadow-[0_20px_50px_rgba(0,0,0,0.04)] mb-10 relative z-10
      `}>
        <div className="p-4">
          {preview ? (
            <div className="relative w-32 h-32 rounded-3xl overflow-hidden border-2 border-slate-100 mb-2 animate-in zoom-in duration-300">
              <img src={preview} alt="Preview" className="w-full h-full object-cover" />
              <button 
                onClick={() => setPreview(null)} 
                className="absolute top-1 right-1 w-6 h-6 bg-black/50 text-white rounded-full flex items-center justify-center backdrop-blur-md hover:bg-black transition-colors"
              >
                ×
              </button>
            </div>
          ) : (
            <textarea 
              id="magic-input"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={placeholder}
              className="w-full bg-transparent border-none focus:ring-0 text-xl font-bold text-slate-800 placeholder:text-slate-300 min-h-[140px] resize-none"
            />
          )}
        </div>

        {/* Action Bar */}
        <div className="flex justify-between items-center p-2 bg-slate-50/80 rounded-[2rem] border border-slate-100/50">
          <div className="flex gap-2 pl-2">
            <button 
              onClick={handleLinkClick} 
              className="w-10 h-10 rounded-full bg-white flex items-center justify-center shadow-sm hover:bg-[#FFE8B5] hover:scale-110 active:scale-90 transition-all text-lg border border-slate-100"
              title="Verify Link"
            >
              🔗
            </button>
            
            <button 
              onClick={() => fileInputRef.current?.click()} 
              className="w-10 h-10 rounded-full bg-white flex items-center justify-center shadow-sm hover:bg-[#D6D3F9] hover:scale-110 active:scale-90 transition-all text-lg border border-slate-100"
              title="Upload Image"
            >
              📷
            </button>

            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleImageUpload} 
              accept="image/*" 
              className="hidden" 
            />
          </div>

          <button 
            onClick={handleVerify}
            disabled={loading || cooldown > 0 || (!content && !preview)}
            className="bg-black text-white px-8 py-3 rounded-full font-bold text-sm hover:shadow-lg active:scale-95 transition-all disabled:opacity-20"
          >
            {loading ? 'Checking...' : cooldown > 0 ? `Wait ${cooldown}s` : 'Verify Now'}
          </button>
        </div>
      </div>

      {/* RESULTS SECTION */}
      {result && (
        <div className="bg-white rounded-[2.5rem] p-8 shadow-2xl shadow-black/5 border border-slate-50 animate-in fade-in slide-in-from-bottom-6 duration-700">
          <div className="flex flex-col items-center gap-8">
            
            <div className="text-center">
              <span className={`text-[11px] font-black uppercase tracking-[0.2em] px-4 py-1.5 rounded-full ${
                result.score <= 3 ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'
              }`}>
                {result.score <= 3 ? '● System Verified Safe' : '● Potential Scam Detected'}
              </span>
            </div>

            <div className="w-full h-4 bg-slate-100 rounded-full relative overflow-hidden">
              <div 
                className={`h-full rounded-full transition-all duration-[1500ms] ease-out ${
                  result.score <= 3 ? 'bg-emerald-400' : 'bg-rose-400'
                }`} 
                style={{ width: `${(result.score / 10) * 100}%` }}
              />
            </div>

            <div className="text-center">
              <p className="text-xl font-bold text-slate-800 leading-tight mb-4">
                "{result.summary}"
              </p>
              
              <div className="flex flex-wrap justify-center gap-2 mb-6">
                {result.flags?.map((flag, i) => (
                  <span key={i} className="px-3 py-1 bg-slate-50 text-[9px] font-bold text-slate-400 rounded-full border border-slate-100 uppercase tracking-wider">
                    {flag.replace('_', ' ')}
                  </span>
                ))}
              </div>
            </div>

            <div className="w-full pt-6 border-t border-slate-50 flex justify-center gap-4">
               <button className="text-[10px] font-black uppercase text-slate-400 hover:text-black transition-colors">
                 Report Error
               </button>
               <button className="bg-slate-900 text-white px-6 py-2 rounded-full text-[10px] font-black uppercase active:scale-95 transition-all">
                 Share Result
               </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default Scanner;