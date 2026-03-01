import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { DashboardStats } from '../services/types';

interface Props {
  state: string;
  county: string;
  activeFilter: string;
  onFilter: (filter: string) => void;
}

export function Dashboard({ state, county, activeFilter, onFilter }: Props) {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getDashboard(state, county)
      .then(r => setStats(r.data))
      .catch(console.error);
  }, [state, county]);

  if (!stats) return null;

  const stat = (label: string, value: number, color: string, filterKey: string) => {
    const isActive = activeFilter === filterKey;
    return (
      <div
        onClick={() => onFilter(isActive ? 'all' : filterKey)}
        style={{
          ...styles.stat,
          borderBottom: isActive ? `3px solid ${color}` : '3px solid transparent',
          cursor: 'pointer',
          opacity: activeFilter !== 'all' && !isActive ? 0.45 : 1,
        }}
        title={isActive ? 'Click to clear filter' : `Filter by ${label}`}
      >
        <div style={{ ...styles.statValue, color }}>{value}</div>
        <div style={styles.statLabel}>{label}</div>
      </div>
    );
  };

  return (
    <div style={styles.container}>
      {stat('Total', stats.total_parcels, '#333', 'all')}
      {stat('Assessed', stats.assessed, '#2196f3', 'assessed')}
      {stat('BID', stats.bids, '#4caf50', 'BID')}
      {stat('Reviewed', stats.reviewed, '#ff9800', 'reviewed')}
      {stat('Approved', stats.approved, '#4caf50', 'approved')}
      {stat('Pending', stats.pending_review, '#999', 'pending_review')}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', gap: '16px', padding: '12px 16px', background: '#f5f5f5', borderBottom: '1px solid #e0e0e0' },
  stat: { textAlign: 'center', padding: '4px 8px', borderRadius: '4px', transition: 'opacity 0.15s, border-color 0.15s' },
  statValue: { fontSize: '20px', fontWeight: 'bold' },
  statLabel: { fontSize: '11px', color: '#888', textTransform: 'uppercase' },
};
