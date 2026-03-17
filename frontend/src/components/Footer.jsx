import React from 'react';

const Footer = () => {
  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  };

  return (
    <footer className="bg-[#0A0A0B] text-white pt-24 pb-12 px-6 mt-20 rounded-t-[3.5rem] relative">
      
      {/* 1. Scroll to Top Button */}
      <div className="absolute -top-6 left-1/2 -translate-x-1/2">
        <button 
          onClick={scrollToTop}
          className="w-12 h-12 bg-white text-black rounded-full flex items-center justify-center shadow-xl hover:scale-110 active:scale-90 transition-all cursor-pointer group"
          aria-label="Scroll to top"
        >
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            className="h-5 w-5 group-hover:-translate-y-1 transition-transform" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 15l7-7 7 7" />
          </svg>
        </button>
      </div>

      <div className="max-w-2xl mx-auto flex flex-col items-center text-center">
        
        {/* 2. Brand Identity */}
        <div className="flex flex-col items-center mb-12">
          <div className="w-14 h-14 bg-white rounded-full flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(255,255,255,0.1)]">
            <span className="text-black text-sm font-black italic">L7</span>
          </div>
          <h3 className="text-2xl font-bold tracking-tight mb-4">Layer 7</h3>
          <p className="text-slate-400 text-sm leading-relaxed max-w-sm">
            Simple, beautiful, and secure. We’re building the future of 
            digital safety for everyone.
          </p>
        </div>

        {/* 3. Centered Navigation Links */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-12 mb-20 w-full max-w-lg">
          <div className="flex flex-col items-center">
            <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-600 mb-4">Product</h4>
            <ul className="space-y-3 text-xs font-bold text-slate-300">
              <li className="hover:text-[#D6D3F9] cursor-pointer transition-colors">Scanner</li>
              <li className="hover:text-[#D6D3F9] cursor-pointer transition-colors">Safety Alerts</li>
            </ul>
          </div>
          <div className="flex flex-col items-center">
            <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-600 mb-4">Legal</h4>
            <ul className="space-y-3 text-xs font-bold text-slate-300">
              <li className="hover:text-[#D6D3F9] cursor-pointer transition-colors">Privacy</li>
              <li className="hover:text-[#D6D3F9] cursor-pointer transition-colors">Terms</li>
            </ul>
          </div>
          <div className="flex flex-col items-center col-span-2 md:col-span-1">
            <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-600 mb-4">Social</h4>
            <ul className="space-y-3 text-xs font-bold text-slate-300">
              <li className="hover:text-[#D6D3F9] cursor-pointer transition-colors">Twitter</li>
              <li className="hover:text-[#D6D3F9] cursor-pointer transition-colors">Instagram</li>
            </ul>
          </div>
        </div>

        {/* 4. Newsletter Section */}
        {/* <div className="w-full max-w-md bg-white/5 border border-white/10 rounded-[2.5rem] p-8 mb-20">
          <h4 className="text-sm font-bold mb-2">Join the inner circle</h4>
          <p className="text-xs text-slate-500 mb-6">Practical safety tips, zero spam.</p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input 
              type="email" 
              placeholder="Your email" 
              className="bg-white/5 border border-white/10 rounded-full px-6 py-3 text-xs flex-1 focus:outline-none focus:border-[#D6D3F9] text-center" 
            />
            <button className="bg-[#D6D3F9] text-black px-8 py-3 rounded-full text-[10px] font-black uppercase hover:bg-white transition-all active:scale-95">
              Subscribe
            </button>
          </div>
        </div> */}

        {/* 5. Bottom Copyright */}
        <div className="w-full pt-8 border-t border-white/5 flex flex-col items-center gap-4">
          <p className="text-[9px] font-bold text-slate-600 uppercase tracking-[0.4em]">
            © 2026 Layer 7 Technology • Stay Safe
          </p>
        </div>

      </div>
    </footer>
  );
};

export default Footer;