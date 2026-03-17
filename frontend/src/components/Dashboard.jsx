import React, { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
} from 'recharts';

const API_URL = import.meta.env.VITE_API_URL;

const Dashboard = () => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  // Dummy fallback data for now
  const dummySummary = {
    totals: {
      scans_24h: 42,
      scans_7d: 210,
      feedback_7d: 15,
    },
    risk_distribution: {
      safe: 60,
      medium: 25,
      high: 15,
    },
    sb_hit_rate: 0.12, // 12%
    daily_scans: [
      { date: 'Mon', count: 20 },
      { date: 'Tue', count: 35 },
      { date: 'Wed', count: 18 },
      { date: 'Thu', count: 40 },
      { date: 'Fri', count: 32 },
      { date: 'Sat', count: 22 },
      { date: 'Sun', count: 27 },
    ],
  };

  useEffect(() => {
    const fetchSummary = async () => {
      if (!API_URL) {
        setSummary(dummySummary);
        return;
      }

      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/metrics/summary`);
        if (!res.ok) throw new Error('Failed to load metrics');
        const data = await res.json();
        setSummary(data);
      } catch (e) {
        console.error('Metrics fetch failed, using dummy data', e);
        setSummary(dummySummary);
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, []);

  if (!summary) {
    return (
      <div className="max-w-5xl mx-auto px-6 pt-20">
        <p className="text-sm text-slate-400 text-center">Loading dashboard…</p>
      </div>
    );
  }

  const { totals, risk_distribution, sb_hit_rate, daily_scans } = summary;

  const riskData = [
    { name: 'Safe', value: risk_distribution.safe },
    { name: 'Medium', value: risk_distribution.medium },
    { name: 'High', value: risk_distribution.high },
  ];

  return (
    <div className="max-w-6xl mx-auto px-6 pt-20">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Layer 7 Dashboard</h1>

      {/* KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100">
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2">
            Scans (Last 24h)
          </p>
          <p className="text-3xl font-extrabold text-slate-900">
            {totals.scans_24h}
          </p>
        </div>

        <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100">
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2">
            Scans (Last 7 days)
          </p>
          <p className="text-3xl font-extrabold text-slate-900">
            {totals.scans_7d}
          </p>
        </div>

        <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100">
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2">
            Feedback (Last 7 days)
          </p>
          <p className="text-3xl font-extrabold text-slate-900">
            {totals.feedback_7d}
          </p>
        </div>
      </div>

      {/* MIDDLE ROW: RISK DISTRIBUTION + SAFE BROWSING */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100 md:col-span-2">
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400 mb-4">
            Risk Distribution (Last 7 days)
          </p>
          <div className="w-full h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#f97373" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100 flex flex-col justify-between">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400 mb-2">
              Google Safe Browsing Hit Rate
            </p>
            <p className="text-3xl font-extrabold text-slate-900 mb-2">
              {(sb_hit_rate * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-slate-500">
              Percentage of scans where the URL is already known as malicious.
            </p>
          </div>
          {loading && (
            <p className="text-[10px] text-slate-400 mt-4">Refreshing…</p>
          )}
        </div>
      </div>

      {/* LINE CHART: DAILY SCANS */}
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100 mb-8">
        <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400 mb-4">
          Scans per Day
        </p>
        <div className="w-full h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={daily_scans}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#4f46e5"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* TODO: add recent feedback table later */}
    </div>
  );
};

export default Dashboard;
