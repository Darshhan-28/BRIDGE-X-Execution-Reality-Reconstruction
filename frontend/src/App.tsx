import { useEffect, useState } from 'react';
import { Link, NavLink, Route, Routes } from 'react-router-dom';
import { api } from './api';
import './App.css';
import Agent from './pages/Agent';
import Audit from './pages/Audit';
import Dashboard from './pages/Dashboard';
import FieldIntelligence from './pages/FieldIntelligence';
import Linker from './pages/Linker';
import Memory from './pages/Memory';
import Review from './pages/Review';
import Schedule from './pages/Schedule';

const NAV: [string, string][] = [
  ['/', 'Overview'],
  ['/field', 'Field Evidence'],
  ['/linker', 'Reconciliation'],
  ['/review', 'Planner Decision'],
  ['/schedule', 'Schedule'],
  ['/memory', 'Project Memory'],
  ['/audit', 'Audit'],
  ['/agent', 'Evidence Q&A'],
];

export default function App() {
  const [health, setHealth] = useState<{ version: string; llm: string } | null>(null);

  useEffect(() => {
    api.health().then((h) => setHealth(h)).catch(() => setHealth(null));
  }, []);

  return (
    <div className="bx">
      <header className="bx-header">
        <Link to="/" className="brand">
          <h1>BRIDGE-X</h1>
          <p>Execution Reality Reconstruction · Field Evidence → Execution Truth</p>
        </Link>
        <nav>
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) => (isActive ? 'active' : '')}>
              {label}
            </NavLink>
          ))}
        </nav>
        <span className={`badge ${health ? 'ok' : 'warn'}`} title={health ? `v${health.version} · LLM ${health.llm}` : 'API offline'}>
          {health ? `API ok · ${health.llm}` : 'API offline'}
        </span>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/field" element={<FieldIntelligence />} />
          <Route path="/linker" element={<Linker />} />
          <Route path="/review" element={<Review />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/memory" element={<Memory />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/agent" element={<Agent />} />
          <Route path="*" element={<p>Not found. <Link to="/">Back to Dashboard</Link>.</p>} />
        </Routes>
      </main>
      <footer className="mut">
        Execution Reality Reconstruction: Field Evidence → Execution Event → L5/L6 Reconciliation → Verification → Human Authorization → Verified Actuals. ·
        Synthetic demonstration data — not real Oil India data.
      </footer>
    </div>
  );
}
