import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { DashboardStats } from '../services/types';

interface Props {
  state: string;
  county: string;
}

export function Dashboard({ state, county }: Props) {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getDashboard(state, county)
      .then(r => setStats(r.data))
      .catch(console.error);
  }, [state, county]);

  if (!stats) return null;

  const stat = (label: string, value: number, color: string) => (
    <div style={styles.stat}>
      <div style={{ ...styles.statValue, color }}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );

  return (
    <div style={styles.container}>
      {stat('Total', stats.total_parcels, '#333')}
      {stat('Assessed', stats.assessed, '#2196f3')}
      {stat('BID', stats.bids, '#4caf50')}
      {stat('Reviewed', stats.reviewed, '#ff9800')}
      {stat('Approved', stats.approved, '#4caf50')}
      {stat('Pending', stats.pending_review, '#999')}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', gap: '16px', padding: '12px 16px', background: '#f5f5f5', borderBottom: '1px solid #e0e0e0' },
  stat: { textAlign: 'center' },
  statValue: { fontSize: '20px', fontWeight: 'bold' },
  statLabel: { fontSize: '11px', color: '#888', textTransform: 'uppercase' },
};
