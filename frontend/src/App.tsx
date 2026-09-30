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
  ['/', 'Dashboard'],
  ['/field', 'Field Intel'],
  ['/linker', 'Linker'],
  ['/review', 'Review'],
  ['/schedule', 'Schedule'],
  ['/memory', 'Memory'],
  ['/audit', 'Audit'],
  ['/agent', 'Time Agent'],
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
          <p>Planning-to-Execution Intelligence</p>
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
        AI proposes. Verification validates. Humans control consequential decisions. ·
        Synthetic demonstration data — not real Oil India data.
      </footer>
    </div>
  );
}
