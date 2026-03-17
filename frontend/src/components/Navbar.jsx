import React from 'react';

const Navbar = ({ onLaunchClick }) => {
  return (
    // The wrapper must be full width (left-0 right-0)
    <header className="fixed top-0 left-0 right-0 z-[100] py-6 px-4">
      {/* This container centers the pill on the screen */}
      <div className="max-w-xl mx-auto">
        <div className="bg-white/90 backdrop-blur-xl border border-white/20 h-16 rounded-full px-6 flex items-center justify-between shadow-lg shadow-black/5">
          
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-black rounded-full flex items-center justify-center">
              <span className="text-white text-[10px] font-black italic">L7</span>
            </div>
            <span className="font-bold tracking-tight text-sm text-slate-900">Layer 7</span>
          </div>
          
          {/* Action Button */}
          <button 
            onClick={onLaunchClick}
            className="bg-black text-white px-5 py-2.5 rounded-full text-[11px] font-bold hover:bg-slate-800 transition-all cursor-pointer active:scale-95"
          >
            Check Now
          </button>
        </div>
      </div>
    </header>
  );
};

export default Navbar;