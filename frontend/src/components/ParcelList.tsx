import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { ParcelSummary } from '../services/types';

interface Props {
  state: string;
  county: string;
  selectedId: number | null;
  onSelect: (id: number) => void;
  activeFilter: string;
  onFilterChange: (filter: string) => void;
}

type SortKey = 'parcel_id' | 'owner_name' | 'billed_amount' | 'decision' | 'risk_score';

export function ParcelList({ state, county, selectedId, onSelect, activeFilter, onFilterChange }: Props) {
  const [parcels, setParcels] = useState<ParcelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('risk_score');
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { state, county, limit: 500 };

    // API-level filtering (efficient for large datasets)
    if (activeFilter === 'BID') params.decision = 'BID';
    if (activeFilter === 'DO_NOT_BID') params.decision = 'DO_NOT_BID';
    if (search) params.search_term = search;

    api.searchParcels(params)
      .then(r => setParcels(r.data.parcels))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [state, county, activeFilter, search]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(a => !a);
    else { setSortKey(key); setSortAsc(true); }
  };

  // Client-side filtering for review/assessment status fields
  const filtered = parcels.filter(p => {
    if (activeFilter === 'assessed') return p.decision != null;
    if (activeFilter === 'reviewed') return p.review_status != null && p.review_status !== 'pending';
    if (activeFilter === 'approved') return p.final_approved === true;
    if (activeFilter === 'pending_review') return p.decision === 'BID' && p.review_status === 'pending';
    return true; // 'all', 'BID', 'DO_NOT_BID' already handled by API or no client filter needed
  });

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortAsc ? cmp : -cmp;
  });

  const arrow = (key: SortKey) => sortKey === key ? (sortAsc ? ' ▲' : ' ▼') : ' ⇅';

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
        <select value={activeFilter} onChange={e => onFilterChange(e.target.value)} style={styles.select}>
          <option value="all">All</option>
          <option value="assessed">Assessed</option>
          <option value="BID">BID only</option>
          <option value="reviewed">Reviewed</option>
          <option value="approved">Approved</option>
          <option value="pending_review">Pending Review</option>
          <option value="DO_NOT_BID">Rejected</option>
        </select>
      </div>

      {loading ? (
        <div style={styles.loading}>Loading...</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.thSort} onClick={() => handleSort('parcel_id')}>Parcel{arrow('parcel_id')}</th>
              <th style={styles.thSort} onClick={() => handleSort('owner_name')}>Owner{arrow('owner_name')}</th>
              <th style={styles.thSort}>Type</th>
              <th style={{ ...styles.thSort, textAlign: 'right' }} onClick={() => handleSort('billed_amount')}>Amount{arrow('billed_amount')}</th>
              <th style={{ ...styles.thSort, textAlign: 'center' }} onClick={() => handleSort('decision')}>Decision{arrow('decision')}</th>
              <th style={{ ...styles.thSort, textAlign: 'center' }} onClick={() => handleSort('risk_score')}>Score{arrow('risk_score')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(p => (
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
                <td style={styles.td}>{p.property_type || '—'}</td>
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
      <div style={styles.count}>{sorted.length} parcels{filtered.length !== parcels.length ? ` (of ${parcels.length} loaded)` : ''}</div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  controls: { display: 'flex', gap: '8px', padding: '12px', borderBottom: '1px solid #e0e0e0' },
  searchInput: { flex: 1, padding: '8px 12px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '14px' },
  select: { padding: '8px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '14px' },
  table: { width: '100%', borderCollapse: 'collapse', flex: 1 },
  thSort: { textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid #ddd', fontSize: '12px', color: '#666', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' },
  td: { padding: '8px 12px', borderBottom: '1px solid #f0f0f0', fontSize: '14px' },
  row: { transition: 'background 0.1s' },
  subtext: { fontSize: '11px', color: '#999', marginTop: '2px' },
  bidBadge: { background: '#4caf50', color: '#fff', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 'bold' },
  rejectBadge: { background: '#f44336', color: '#fff', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 'bold' },
  pendingBadge: { color: '#999' },
  loading: { padding: '40px', textAlign: 'center', color: '#999' },
  count: { padding: '8px 12px', fontSize: '12px', color: '#999', borderTop: '1px solid #e0e0e0' },
};
