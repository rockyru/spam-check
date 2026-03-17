import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

const Navbar = ({ onScanClick }) => {
  const navigate = useNavigate();

  const handleCheckNow = () => {
    // If we are already on the home page, scroll to scanner
    if (window.location.pathname === '/') {
      onScanClick();
    } else {
      // If we are on dashboard, go home first then scroll
      navigate('/');
      setTimeout(onScanClick, 100);
    }
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-[100] py-6 px-4">
      <div className="max-w-xl mx-auto">
        <div className="bg-white/90 backdrop-blur-xl border border-white/20 h-16 rounded-full px-6 flex items-center justify-between shadow-lg shadow-black/5">
          
          {/* Brand - Links to Home */}
          <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="w-8 h-8 bg-black rounded-full flex items-center justify-center">
              <span className="text-white text-[10px] font-black italic">L7</span>
            </div>
            <span className="font-bold tracking-tight text-sm text-slate-900">Layer 7</span>
          </Link>
          
          <div className="flex gap-2">
            {/* Navigates to /dashboard */}
            <Link 
              to="/dashboard"
              className="bg-slate-100 text-slate-900 px-5 py-2.5 rounded-full text-[11px] font-bold hover:bg-slate-200 transition-all active:scale-95"
            >
              Metrics
            </Link>

            {/* Triggers the Scroll logic */}
            <button 
              onClick={handleCheckNow}
              className="bg-black text-white px-5 py-2.5 rounded-full text-[11px] font-bold hover:bg-slate-800 transition-all active:scale-95"
            >
              Check Now
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;