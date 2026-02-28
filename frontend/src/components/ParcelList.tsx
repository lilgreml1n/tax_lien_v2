import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { ParcelSummary } from '../services/types';

interface Props {
  state: string;
  county: string;
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function ParcelList({ state, county, selectedId, onSelect }: Props) {
  const [parcels, setParcels] = useState<ParcelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { state, county, limit: 200 };
    if (filter === 'BID') params.decision = 'BID';
    if (filter === 'DO_NOT_BID') params.decision = 'DO_NOT_BID';
    if (search) params.search_term = search;

    api.searchParcels(params)
      .then(r => setParcels(r.data.parcels))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [state, county, filter, search]);

  const badge = (decision: string | null) => {
    if (decision === 'BID') return <span style={styles.bidBadge}>BID</span>;
    if (decision === 'DO_NOT_BID') return <span style={styles.rejectBadge}>REJECT</span>;
    return <span style={styles.pendingBadge}>—</span>;
  };

  return (
    <div style={styles.container}>
      <div style={styles.controls}>
        <input
          type="text"
          placeholder="Search parcel, owner, address..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={styles.searchInput}
        />
        <select value={filter} onChange={e => setFilter(e.target.value)} style={styles.select}>
          <option value="all">All</option>
          <option value="BID">BID only</option>
          <option value="DO_NOT_BID">Rejected</option>
        </select>
      </div>

      {loading ? (
        <div style={styles.loading}>Loading...</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Parcel</th>
              <th style={styles.th}>Owner</th>
              <th style={{ ...styles.th, textAlign: 'right' }}>Amount</th>
              <th style={{ ...styles.th, textAlign: 'center' }}>Decision</th>
              <th style={{ ...styles.th, textAlign: 'center' }}>Score</th>
            </tr>
          </thead>
          <tbody>
            {parcels.map(p => (
              <tr
                key={p.id}
                onClick={() => onSelect(p.id)}
                style={{
                  ...styles.row,
                  backgroundColor: p.id === selectedId ? '#e3f2fd' : undefined,
                  cursor: 'pointer',
                }}
              >
                <td style={styles.td}>
                  <strong>{p.parcel_id}</strong>
                  {p.full_address && <div style={styles.subtext}>{p.full_address}</div>}
                </td>
                <td style={styles.td}>{p.owner_name || '—'}</td>
                <td style={{ ...styles.td, textAlign: 'right' }}>
                  {p.billed_amount != null ? `$${p.billed_amount.toFixed(2)}` : '—'}
                </td>
                <td style={{ ...styles.td, textAlign: 'center' }}>{badge(p.decision)}</td>
                <td style={{ ...styles.td, textAlign: 'center' }}>{p.risk_score ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div style={styles.count}>{parcels.length} parcels</div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  controls: { display: 'flex', gap: '8px', padding: '12px', borderBottom: '1px solid #e0e0e0' },
  searchInput: { flex: 1, padding: '8px 12px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '14px' },
  select: { padding: '8px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '14px' },
  table: { width: '100%', borderCollapse: 'collapse', flex: 1 },
  th: { textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid #ddd', fontSize: '12px', color: '#666', textTransform: 'uppercase' },
  td: { padding: '8px 12px', borderBottom: '1px solid #f0f0f0', fontSize: '14px' },
  row: { transition: 'background 0.1s' },
  subtext: { fontSize: '11px', color: '#999', marginTop: '2px' },
  bidBadge: { background: '#4caf50', color: '#fff', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 'bold' },
  rejectBadge: { background: '#f44336', color: '#fff', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 'bold' },
  pendingBadge: { color: '#999' },
  loading: { padding: '40px', textAlign: 'center', color: '#999' },
  count: { padding: '8px 12px', fontSize: '12px', color: '#999', borderTop: '1px solid #e0e0e0' },
};
