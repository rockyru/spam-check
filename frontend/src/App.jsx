// src/App.jsx
import React, { useRef } from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Scanner from './components/Scanner';
import Footer from './components/Footer';
import Dashboard from './components/Dashboard';

function App() {
  const scannerRef = useRef(null);

  return (
    <div className="relative min-h-screen bg-[#F4F3F8] bg-blueprint selection:bg-[#D6D3F9]">
      <Navbar onLaunchClick={() => scannerRef.current?.scrollIntoView({ behavior: 'smooth' })} />

      <Routes>
        <Route
          path="/"
          element={
            <>
              <Hero onStartClick={() => scannerRef.current?.scrollIntoView({ behavior: 'smooth' })} />
              <Scanner scannerRef={scannerRef} />
            </>
          }
        />
        <Route
          path="/dashboard"
          element={
            <div className="pt-8 pb-16">
              <Dashboard />
            </div>
          }
        />
      </Routes>

      <Footer />
    </div>
  );
}

export default App;
