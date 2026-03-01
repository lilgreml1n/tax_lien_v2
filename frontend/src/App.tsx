import { useState, useEffect } from 'react';
import { ParcelList } from './components/ParcelList';
import { ParcelDetail } from './components/ParcelDetail';
import { Dashboard } from './components/Dashboard';
import { NotificationToggle } from './components/NotificationToggle';
import { UpcomingEvents } from './components/UpcomingEvents';
import { api } from './services/api';
import './App.css';

interface CountyOption {
  state: string;
  county: string;
}

function App() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const [counties, setCounties] = useState<CountyOption[]>([]);
  const [state, setState] = useState('Arizona');
  const [county, setCounty] = useState('Apache');

  // Load available counties from registered scrapers
  useEffect(() => {
    api.getConfigs()
      .then(r => {
        const options = r.data.map(c => ({ state: c.state, county: c.county }));
        if (options.length > 0) {
          setCounties(options);
          // Keep current selection if still valid, otherwise default to first
          const stillValid = options.some(o => o.state === state && o.county === county);
          if (!stillValid) {
            setState(options[0].state);
            setCounty(options[0].county);
          }
        }
      })
      .catch(() => {
        // API unreachable — fall back to Apache
        setCounties([{ state: 'Arizona', county: 'Apache' }]);
      });
  }, []);

  const handleCountyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const [s, c] = e.target.value.split('|');
    setState(s);
    setCounty(c);
    setSelectedId(null);
    setActiveFilter('all');
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>🏘️ LienHunter</h1>
        <select
          value={`${state}|${county}`}
          onChange={handleCountyChange}
          style={styles.countyPicker}
        >
          {counties.map(o => (
            <option key={`${o.state}|${o.county}`} value={`${o.state}|${o.county}`}>
              {o.state} / {o.county}
            </option>
          ))}
        </select>
        <UpcomingEvents />
        <NotificationToggle />
      </header>
      <Dashboard state={state} county={county} activeFilter={activeFilter} onFilter={setActiveFilter} />
      <div className="app-body">
        <div className="app-list">
          <ParcelList
            state={state}
            county={county}
            selectedId={selectedId}
            onSelect={setSelectedId}
            activeFilter={activeFilter}
            onFilterChange={setActiveFilter}
          />
        </div>
        <div className="app-detail">
          {selectedId ? (
            <ParcelDetail parcelId={selectedId} onClose={() => setSelectedId(null)} />
          ) : (
            <div className="app-empty">
              ← Select a parcel to review
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  countyPicker: {
    padding: '6px 12px',
    borderRadius: '6px',
    border: 'none',
    background: 'rgba(255,255,255,0.2)',
    color: '#fff',
    fontSize: '14px',
    fontWeight: 'bold',
    cursor: 'pointer',
  },
};

export default App;
