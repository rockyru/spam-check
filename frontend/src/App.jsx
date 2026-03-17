import React, { useRef } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Scanner from './components/Scanner';
import Footer from './components/Footer';

function App() {
  const scannerRef = useRef(null);

  return (
   <div className="relative min-h-screen bg-[#F4F3F8] bg-blueprint selection:bg-[#D6D3F9]">
      <Navbar onLaunchClick={() => scannerRef.current?.scrollIntoView({ behavior: 'smooth' })} />
      <Hero onStartClick={() => scannerRef.current?.scrollIntoView({ behavior: 'smooth' })} />
      <Scanner scannerRef={scannerRef} />
      <Footer />
    </div>
  );
}

export default App;