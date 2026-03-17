import React from 'react';

const Hero = ({ onStartClick }) => {
  return (
    <section className="relative pt-40 pb-20 px-6 overflow-hidden">
      {/* Decorative Wave - Cooper Style */}
      <div className="absolute top-20 -right-20 opacity-10 pointer-events-none rotate-12 select-none">
        <svg width="600" height="200" viewBox="0 0 600 200">
          <path id="curve" d="M0,100 C150,200 450,0 600,100" fill="transparent" stroke="black" strokeWidth="1"/>
          <text className="text-[18px] font-black uppercase tracking-[12px]">
            <textPath href="#curve">
              Stop guessing • Stay safe online • Trust your tech • 
            </textPath>
          </text>
        </svg>
      </div>

      <div className="max-w-xl mx-auto text-center relative z-10">
        {/* Playful Tagline */}
        <div className="inline-block px-4 py-1.5 bg-white border border-slate-100 rounded-full shadow-sm mb-8">
          <span className="text-[10px] font-black text-[#FF7070] uppercase tracking-widest">
            Your Digital Bodyguard
          </span>
        </div>
        
        {/* Main Heading */}
        <h1 className="text-6xl font-extrabold tracking-tight text-slate-900 mb-6 leading-[1.1]">
          Is it real or <br /> 
          <span className="text-[#D6D3F9] italic">is it a scam?</span>
        </h1>
        
        {/* Consumer-Focused Subtext */}
        <p className="text-slate-500 font-medium text-lg leading-relaxed mb-10 px-4">
          Don't let suspicious links or fake messages ruin your day. 
          Drop any link, text, or photo here and we'll check it for you.
        </p>
        
        {/* Call to Action */}
        <div className="flex flex-col items-center gap-4">
          <button 
            onClick={onStartClick}
            className="bg-black text-white px-12 py-5 rounded-[2.5rem] font-bold text-lg hover:shadow-2xl hover:-translate-y-1 transition-all cursor-pointer shadow-xl shadow-black/10 active:scale-95"
          >
            Check something now
          </button>
          
          {/* <div className="flex items-center gap-2 mt-4">
            <div className="flex -space-x-2">
              {[1,2,3].map(i => (
                <div key={i} className={`w-6 h-6 rounded-full border-2 border-white bg-slate-200`} />
              ))}
            </div>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">
              Used by 12,000+ people today
            </p>
          </div> */}
        </div>
      </div>
    </section>
  );
};

export default Hero;