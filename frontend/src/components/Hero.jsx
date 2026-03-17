import React from 'react';

const Hero = ({ onStartClick }) => {
  return (
    <section className="relative pt-40 pb-20 px-6 overflow-hidden">
      {/* Decorative Wave */}
      <div className="absolute top-20 -right-20 opacity-10 pointer-events-none rotate-12 select-none">
        <svg width="600" height="200" viewBox="0 0 600 200">
          <path id="curve" d="M0,100 C150,200 450,0 600,100" fill="transparent" stroke="black" strokeWidth="1" />
          <text className="text-[18px] font-black uppercase tracking-[12px]">
            <textPath href="#curve">
              Stop guessing • Stay safe online • Trust your tech • 
            </textPath>
          </text>
        </svg>
      </div>

      <div className="max-w-xl mx-auto text-center relative z-10">
        {/* Tagline */}
        <div className="inline-block px-4 py-1.5 bg-white border border-slate-100 rounded-full shadow-sm mb-8">
          <span className="text-[10px] font-black text-[#FF7070] uppercase tracking-widest">
            Crowd‑backed scam scanner
          </span>
        </div>

        {/* Heading */}
        <h1 className="text-6xl font-extrabold tracking-tight text-slate-900 mb-6 leading-[1.1]">
          Is it real or <br />
          <span className="text-[#D6D3F9] italic">is it a scam?</span>
        </h1>
       

        {/* Subtext with “legit” signal */}
        <p className="text-slate-500 font-medium text-lg leading-relaxed mb-10 px-4">
          Paste any link, message, or screenshot. We compare it against
          trusted security sources and anonymous reports from other people
          who’ve seen the same scams.
        </p>
        
        {/* Call to Action */}
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={onStartClick}
            className="bg-black text-white px-12 py-5 rounded-[2.5rem] font-bold text-lg hover:shadow-2xl hover:-translate-y-1 transition-all cursor-pointer shadow-xl shadow-black/10 active:scale-95"
          >
            Scam Check
          </button>

         
        </div>
      </div>
    </section>
  );
};

export default Hero;
