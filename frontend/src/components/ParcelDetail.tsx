import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { ParcelDetail as ParcelDetailType } from '../services/types';
import { ReviewForm } from './ReviewForm';

interface Props {
  parcelId: number;
}

export function ParcelDetail({ parcelId }: Props) {
  const [parcel, setParcel] = useState<ParcelDetailType | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDetail = () => {
    setLoading(true);
    api.getParcelDetail(parcelId)
      .then(r => setParcel(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchDetail(); }, [parcelId]);

  if (loading) return <div style={styles.loading}>Loading...</div>;
  if (!parcel) return <div style={styles.loading}>Parcel not found</div>;

  const link = (url: string | null, label: string, emoji: string) =>
    url ? (
      <a href={url} target="_blank" rel="noopener noreferrer" style={styles.link}>
        {emoji} {label}
      </a>
    ) : null;

  const decisionColor = parcel.decision === 'BID' ? '#4caf50' : parcel.decision === 'DO_NOT_BID' ? '#f44336' : '#999';

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.title}>{parcel.parcel_id}</h2>
        {parcel.decision && (
          <span style={{ ...styles.decisionBadge, background: decisionColor }}>
            {parcel.decision === 'DO_NOT_BID' ? 'REJECT' : parcel.decision}
          </span>
        )}
        {parcel.risk_score != null && (
          <span style={styles.score}>Score: {parcel.risk_score}</span>
        )}
      </div>

      {/* Property Info */}
      <div style={styles.section}>
        <div style={styles.grid}>
          <div>
            <div style={styles.label}>Address</div>
            <div>{parcel.full_address || parcel.address || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Owner</div>
            <div>{parcel.owner_name || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Billed Amount</div>
            <div style={styles.amount}>
              {parcel.billed_amount != null ? `$${parcel.billed_amount.toFixed(2)}` : '—'}
            </div>
          </div>
          <div>
            <div style={styles.label}>Max Bid</div>
            <div>{parcel.max_bid != null ? `$${parcel.max_bid.toFixed(2)}` : '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Lot Size</div>
            <div>{parcel.lot_size_acres ? `${parcel.lot_size_acres} acres` : '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Assessed Value</div>
            <div>{parcel.assessed_total_value != null ? `$${parcel.assessed_total_value.toFixed(2)}` : '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Legal Class</div>
            <div>{parcel.legal_class || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Zoning</div>
            <div>{parcel.zoning_code || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Property Type</div>
            <div>{parcel.property_type || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Ownership</div>
            <div>{parcel.ownership_type || '—'}</div>
          </div>
        </div>

        {parcel.kill_switch && (
          <div style={styles.killSwitch}>
            ⚠️ Kill Switch: {parcel.kill_switch}
          </div>
        )}
        {parcel.critical_warning && (
          <div style={styles.warning}>
            ⚡ {parcel.critical_warning}
          </div>
        )}
        {parcel.legal_description && (
          <div style={{ marginTop: '8px' }}>
            <div style={styles.label}>Legal Description</div>
            <div style={styles.legalDesc}>{parcel.legal_description}</div>
          </div>
        )}
      </div>

      {/* Links */}
      <div style={styles.linkBar}>
        {link(parcel.google_maps_url, 'Maps', '🗺️')}
        {link(parcel.street_view_url, 'Street View', '👁️')}
        {link(parcel.zillow_url, 'Zillow', '💰')}
        {link(parcel.realtor_url, 'Realtor', '🏠')}
        {link(parcel.assessor_url, 'Assessor', '🏛️')}
        {link(parcel.treasurer_url, 'Treasurer', '💵')}
      </div>

      {/* Review Form */}
      <ReviewForm parcel={parcel} onSaved={fetchDetail} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '20px', overflowY: 'auto', height: '100%', boxSizing: 'border-box' },
  header: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' },
  title: { margin: 0, fontSize: '22px' },
  decisionBadge: { color: '#fff', padding: '4px 12px', borderRadius: '12px', fontSize: '13px', fontWeight: 'bold' },
  score: { fontSize: '14px', color: '#666', marginLeft: 'auto' },
  section: { marginBottom: '16px', padding: '16px', background: '#f9f9f9', borderRadius: '6px', border: '1px solid #e0e0e0' },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' },
  label: { fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '2px' },
  amount: { fontSize: '16px', fontWeight: 'bold', color: '#d32f2f' },
  killSwitch: { marginTop: '12px', padding: '8px 12px', background: '#fff3e0', border: '1px solid #ff9800', borderRadius: '4px', fontSize: '13px' },
  warning: { marginTop: '8px', padding: '8px 12px', background: '#fce4ec', border: '1px solid #ef5350', borderRadius: '4px', fontSize: '13px' },
  legalDesc: { fontSize: '12px', color: '#555', fontStyle: 'italic' },
  linkBar: { display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' },
  link: { padding: '6px 12px', background: '#e3f2fd', color: '#1565c0', borderRadius: '4px', textDecoration: 'none', fontSize: '13px', border: '1px solid #90caf9' },
  loading: { padding: '40px', textAlign: 'center', color: '#999' },
};
