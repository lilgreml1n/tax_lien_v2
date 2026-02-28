import { useState } from 'react';
import { ParcelList } from './components/ParcelList';
import { ParcelDetail } from './components/ParcelDetail';
import { Dashboard } from './components/Dashboard';
import './App.css';

const STATE = 'Arizona';
const COUNTY = 'Apache';

function App() {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  return (
    <div className="app">
      <header className="app-header">
        <h1>🏘️ LienHunter</h1>
        <span className="app-subtitle">{STATE} / {COUNTY}</span>
      </header>
      <Dashboard state={STATE} county={COUNTY} />
      <div className="app-body">
        <div className="app-list">
          <ParcelList
            state={STATE}
            county={COUNTY}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>
        <div className="app-detail">
          {selectedId ? (
            <ParcelDetail parcelId={selectedId} />
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

export default App;

