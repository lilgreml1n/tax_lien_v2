import { useState, useEffect } from 'react';
import { api } from '../services/api';

export function NotificationToggle() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getNotificationsStatus()
      .then(r => setEnabled(r.data.notifications_enabled))
      .catch(() => setEnabled(null));
  }, []);

  const toggle = async () => {
    if (loading || enabled === null) return;
    setLoading(true);
    try {
      const res = enabled
        ? await api.disableNotifications()
        : await api.enableNotifications();
      setEnabled(res.data.notifications_enabled);
    } catch {
      // silently ignore
    } finally {
      setLoading(false);
    }
  };

  if (enabled === null) return null;

  return (
    <button
      onClick={toggle}
      disabled={loading}
      title={enabled ? 'Reminders ON — click to disable' : 'Reminders OFF — click to enable'}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        background: enabled ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.05)',
        border: `1px solid ${enabled ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)'}`,
        borderRadius: '6px',
        color: enabled ? '#fff' : 'rgba(255,255,255,0.4)',
        fontSize: '13px',
        padding: '5px 10px',
        cursor: loading ? 'wait' : 'pointer',
        transition: 'all 0.2s',
        marginLeft: 'auto',
      }}
    >
      <span style={{ fontSize: '15px' }}>{enabled ? '🔔' : '🔕'}</span>
      <span>{loading ? '...' : enabled ? 'Reminders on' : 'Reminders off'}</span>
    </button>
  );
}
