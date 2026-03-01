import { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import type { ParcelDetail as ParcelDetailType } from '../services/types';
import { ReviewForm } from './ReviewForm';

function Tip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  return (
    <span
      ref={ref}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      style={{ position: 'relative', display: 'inline-block', marginLeft: '4px', cursor: 'help', color: '#aaa', fontSize: '11px' }}
    >
      ⓘ
      {show && (
        <span style={{
          position: 'absolute', left: '50%', bottom: '120%', transform: 'translateX(-50%)',
          background: '#333', color: '#fff', padding: '6px 10px', borderRadius: '6px',
          fontSize: '12px', whiteSpace: 'normal', width: '220px', lineHeight: '1.4',
          zIndex: 100, boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          pointerEvents: 'none',
        }}>
          {text}
          <span style={{ position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
            borderWidth: '5px', borderStyle: 'solid', borderColor: '#333 transparent transparent transparent' }} />
        </span>
      )}
    </span>
  );
}

interface Props {
  parcelId: number;
  onClose: () => void;
}

export function ParcelDetail({ parcelId, onClose }: Props) {
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
        <button onClick={onClose} style={styles.backBtn}>← Back</button>
        {parcel.assessor_url ? (
          <a href={parcel.assessor_url} target="_blank" rel="noopener noreferrer" style={styles.titleLink}>
            {parcel.parcel_id} ↗
          </a>
        ) : (
          <h2 style={styles.title}>{parcel.parcel_id}</h2>
        )}
        {parcel.decision && (
          <span style={{ ...styles.decisionBadge, background: decisionColor }}>
            {parcel.decision === 'DO_NOT_BID' ? 'REJECT' : parcel.decision}
          </span>
        )}
        {parcel.risk_score != null && (
          <span style={styles.score}>
            Score: {parcel.risk_score}
            <Tip text="Capital Guardian AI score 0–100. Higher = stronger investment. 85+ is confident, 65–84 has some unknowns, below 65 is marginal. Not a redemption probability — rates overall attractiveness." />
          </span>
        )}
      </div>

      {/* Property Info */}
      <div style={styles.section}>
        <div style={styles.grid}>
          <div>
            <div style={styles.label}>Address<Tip text="Situs address from the county assessor. For vacant lots this is often the nearest county road from ESRI geocoding — use the Maps link for exact location." /></div>
            <div>{parcel.full_address || parcel.address || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Owner<Tip text="Registered owner name from the county assessor. LLCs and trusts are common. 'Estate of' names often signal inherited/unmanaged property — higher chance of non-redemption." /></div>
            <div>{parcel.owner_name || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Billed Amount<Tip text="The delinquent tax amount owed for this lien. This is what you pay at auction to acquire the lien. Arizona charges 16% annual interest on this amount if the owner redeems." /></div>
            <div style={styles.amount}>
              {parcel.billed_amount != null ? `$${parcel.billed_amount.toFixed(2)}` : '—'}
            </div>
          </div>
          <div>
            <div style={styles.label}>Max Bid<Tip text="Capital Guardian's recommended maximum to bid at auction. Calculated as billed amount × 1.10 — a 10% buffer. Never bid above this or your yield drops below acceptable returns." /></div>
            <div>{parcel.max_bid != null ? `$${parcel.max_bid.toFixed(2)}` : '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Lot Size<Tip text="Parcel area in acres from the county assessor's Parcel Detail document. Under 0.25 acres in a rural area may limit development options." /></div>
            <div>{parcel.lot_size_acres ? `${parcel.lot_size_acres} acres` : '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Assessed Value<Tip text="Full Cash Value (FCV) — the county's estimate of market value. Key ratio: assessed value ÷ billed amount should be 10× or more for a safe equity cushion." /></div>
            <div>{parcel.assessed_total_value != null ? `$${parcel.assessed_total_value.toFixed(2)}` : '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Legal Class<Tip text="Arizona property classification. 02.R = residential vacant land (best for tax liens). 03 = agricultural. 04/05 = commercial/industrial. Non-residential classes are auto-rejected." /></div>
            <div>{parcel.legal_class || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Zoning<Tip text="County zoning designation. Determines what can be built on the parcel. Residential zoning (R-1, RU) is preferred. Industrial or commercial zoning raises liability concerns." /></div>
            <div>{parcel.zoning_code || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Property Type<Tip text="AI-classified property type based on assessor data and legal description. Vacant land is the most common for Apache County tax liens." /></div>
            <div>{parcel.property_type || '—'}</div>
          </div>
          <div>
            <div style={styles.label}>Ownership<Tip text="AI-classified ownership structure. Individual, LLC, trust, corporation. Absentee owners (mailing address ≠ property) are more likely to let the lien go unredeemed." /></div>
            <div>{parcel.ownership_type || '—'}</div>
          </div>
        </div>

        {parcel.kill_switch && (
          <div style={styles.killSwitch}>
            ⚠️ Kill Switch: {parcel.kill_switch}
            <Tip text="Hard auto-reject caught before AI ran. Reasons: prohibited legal class, bankruptcy/IRS owner, shack value (<$10k improvement), lot too small (<2,500 sqft), or environmental keyword in legal description." />
          </div>
        )}
        {parcel.critical_warning && (
          <div style={styles.warning}>
            ⚡ {parcel.critical_warning}
            <Tip text="AI-identified concern that didn't auto-reject but needs manual review before bidding." />
          </div>
        )}
        {parcel.legal_description && (
          <div style={{ marginTop: '8px' }}>
            <div style={styles.label}>Legal Description<Tip text="Formal property description from the assessor — subdivision, block, lot, section/township/range. Verify this matches the parcel on the map before bidding." /></div>
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
  titleLink: { margin: 0, fontSize: '22px', fontWeight: 'bold', color: '#1565c0', textDecoration: 'none' },
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
  backBtn: { padding: '4px 10px', fontSize: '13px', cursor: 'pointer', background: 'none', border: '1px solid #ccc', borderRadius: '4px', color: '#555' },
};
