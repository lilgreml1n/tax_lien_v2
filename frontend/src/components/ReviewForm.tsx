import { useState } from 'react';
import { api } from '../services/api';
import type { ParcelDetail } from '../services/types';

interface Props {
  parcel: ParcelDetail;
  onSaved: () => void;
}

export function ReviewForm({ parcel, onSaved }: Props) {
  const [form, setForm] = useState({
    check_street_view: !!parcel.check_street_view,
    check_street_view_notes: parcel.check_street_view_notes || '',
    check_power_lines: !!parcel.check_power_lines,
    check_topography: !!parcel.check_topography,
    check_topography_notes: parcel.check_topography_notes || '',
    check_water_test: !!parcel.check_water_test,
    check_water_notes: parcel.check_water_notes || '',
    check_access_frontage: !!parcel.check_access_frontage,
    check_frontage_ft: parcel.check_frontage_ft,
    check_rooftop_count: !!parcel.check_rooftop_count,
    check_rooftop_pct: parcel.check_rooftop_pct,
    final_legal_matches_map: !!parcel.final_legal_matches_map,
    final_hidden_structure: !!parcel.final_hidden_structure,
    final_who_cuts_grass: parcel.final_who_cuts_grass || '',
    final_approved: parcel.final_approved,
    reviewer_notes: parcel.reviewer_notes || '',
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const set = (field: string, value: unknown) => setForm(prev => ({ ...prev, [field]: value }));

  const save = async (approved?: boolean) => {
    setSaving(true);
    setMsg('');
    try {
      const data = { ...form } as Record<string, unknown>;
      if (approved !== undefined) {
        data.final_approved = approved;
        data.review_status = approved ? 'approved' : 'rejected';
      }
      await api.updateAssessment(parcel.id, data);
      setMsg('✓ Saved');
      onSaved();
    } catch {
      setMsg('✗ Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const check = (label: string, field: string, notesField?: string) => (
    <div style={styles.checkRow}>
      <label style={styles.checkLabel}>
        <input
          type="checkbox"
          checked={form[field as keyof typeof form] as boolean}
          onChange={e => set(field, e.target.checked)}
        />
        {' '}{label}
      </label>
      {notesField && form[field as keyof typeof form] && (
        <input
          type="text"
          placeholder="Notes..."
          value={(form[notesField as keyof typeof form] as string) || ''}
          onChange={e => set(notesField, e.target.value)}
          style={styles.notesInput}
        />
      )}
    </div>
  );

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>Manual Review Checklist</h3>

      {check('Street View verified', 'check_street_view', 'check_street_view_notes')}
      {check('Power lines/poles visible', 'check_power_lines')}
      {check('Topography checked', 'check_topography', 'check_topography_notes')}
      {check('Water access checked', 'check_water_test', 'check_water_notes')}
      {check('Access/frontage verified', 'check_access_frontage')}
      {form.check_access_frontage && (
        <input
          type="number"
          placeholder="Frontage (ft)"
          value={form.check_frontage_ft ?? ''}
          onChange={e => set('check_frontage_ft', e.target.value ? Number(e.target.value) : null)}
          style={{ ...styles.notesInput, width: '140px' }}
        />
      )}
      {check('Rooftops counted', 'check_rooftop_count')}

      <hr style={styles.divider} />
      <h4 style={styles.subheading}>Final Boss</h4>

      {check('Legal description matches map', 'final_legal_matches_map')}
      {check('Hidden structures found', 'final_hidden_structure')}

      <div style={styles.checkRow}>
        <label style={styles.checkLabel}>Who cuts grass?</label>
        <input
          type="text"
          value={form.final_who_cuts_grass}
          onChange={e => set('final_who_cuts_grass', e.target.value)}
          style={styles.notesInput}
        />
      </div>

      <textarea
        placeholder="Reviewer notes..."
        value={form.reviewer_notes}
        onChange={e => set('reviewer_notes', e.target.value)}
        style={styles.textarea}
      />

      <div style={styles.actions}>
        <button onClick={() => save(true)} disabled={saving} style={styles.approveBtn}>
          ✓ APPROVE
        </button>
        <button onClick={() => save(false)} disabled={saving} style={styles.rejectBtn}>
          ✗ REJECT
        </button>
        <button onClick={() => save()} disabled={saving} style={styles.saveBtn}>
          Save Draft
        </button>
        {msg && <span style={{ marginLeft: '12px', fontSize: '14px' }}>{msg}</span>}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '16px', background: '#fafafa', borderRadius: '6px', border: '1px solid #e0e0e0' },
  heading: { margin: '0 0 12px', fontSize: '16px' },
  subheading: { margin: '8px 0', fontSize: '14px', color: '#555' },
  checkRow: { marginBottom: '8px' },
  checkLabel: { fontSize: '14px', cursor: 'pointer' },
  notesInput: { display: 'block', marginTop: '4px', marginLeft: '24px', padding: '4px 8px', border: '1px solid #ccc', borderRadius: '3px', fontSize: '13px', width: '90%' },
  divider: { border: 'none', borderTop: '1px solid #ddd', margin: '12px 0' },
  textarea: { width: '100%', height: '60px', padding: '8px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '13px', resize: 'vertical' as const, marginBottom: '12px', boxSizing: 'border-box' as const },
  actions: { display: 'flex', gap: '8px', alignItems: 'center' },
  approveBtn: { padding: '8px 16px', background: '#4caf50', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px' },
  rejectBtn: { padding: '8px 16px', background: '#f44336', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px' },
  saveBtn: { padding: '8px 16px', background: '#2196f3', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '14px' },
};
