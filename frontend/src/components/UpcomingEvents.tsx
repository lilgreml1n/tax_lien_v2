import { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';

interface CalendarEvent {
  id: number;
  state: string;
  county: string;
  event_date: string;
  event_type: string;
  url: string | null;
  notes: string | null;
  reminder_7d_sent: number;
  reminder_3d_sent: number;
  reminder_1d_sent: number;
  reminder_0d_sent: number;
}

function daysUntil(dateStr: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const event = new Date(dateStr + 'T00:00:00');
  return Math.round((event.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function urgencyColor(days: number): string {
  if (days < 0)  return '#999';   // past
  if (days <= 3) return '#f44336'; // red — imminent
  if (days <= 7) return '#ff9800'; // orange — this week
  if (days <= 30) return '#2196f3'; // blue — this month
  return '#4caf50';                 // green — future
}

function urgencyLabel(days: number): string {
  if (days < 0)  return `${Math.abs(days)}d ago`;
  if (days === 0) return 'TODAY';
  if (days === 1) return 'TOMORROW';
  return `in ${days}d`;
}

export function UpcomingEvents() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getUpcomingEvents().then(r => setEvents(r.data)).catch(() => {});
  }, []);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Only show future + today events in badge count
  const upcoming = events
    .map(e => ({ ...e, days: daysUntil(e.event_date) }))
    .filter(e => e.days >= 0)
    .sort((a, b) => a.days - b.days);

  const urgent = upcoming.filter(e => e.days <= 7).length;

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        title="Upcoming auction dates"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: open ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.1)',
          border: '1px solid rgba(255,255,255,0.25)',
          borderRadius: '6px',
          color: '#fff',
          fontSize: '13px',
          padding: '5px 10px',
          cursor: 'pointer',
          transition: 'background 0.2s',
        }}
      >
        <span style={{ fontSize: '15px' }}>📅</span>
        <span>Watching</span>
        {urgent > 0 && (
          <span style={{
            background: '#f44336',
            borderRadius: '10px',
            fontSize: '11px',
            fontWeight: 'bold',
            padding: '1px 6px',
            lineHeight: '16px',
          }}>
            {urgent}
          </span>
        )}
        {urgent === 0 && upcoming.length > 0 && (
          <span style={{
            background: 'rgba(255,255,255,0.25)',
            borderRadius: '10px',
            fontSize: '11px',
            padding: '1px 6px',
            lineHeight: '16px',
          }}>
            {upcoming.length}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          width: '320px',
          background: '#fff',
          borderRadius: '8px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          zIndex: 1000,
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '10px 14px',
            background: '#1a237e',
            color: '#fff',
            fontSize: '13px',
            fontWeight: 600,
          }}>
            Watched Auctions ({upcoming.length})
          </div>

          {upcoming.length === 0 ? (
            <div style={{ padding: '16px', color: '#999', fontSize: '13px', textAlign: 'center' }}>
              No upcoming events
            </div>
          ) : (
            <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
              {upcoming.map(e => (
                <div key={e.id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '10px 14px',
                  borderBottom: '1px solid #f0f0f0',
                  gap: '10px',
                }}>
                  {/* Urgency dot */}
                  <div style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: urgencyColor(e.days),
                    flexShrink: 0,
                  }} />

                  {/* County + date */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '13px', color: '#333' }}>
                      {e.county} County, {e.state}
                    </div>
                    <div style={{ fontSize: '12px', color: '#888', marginTop: '2px' }}>
                      {new Date(e.event_date + 'T00:00:00').toLocaleDateString('en-US', {
                        weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
                      })}
                    </div>
                    {e.notes && (
                      <div style={{
                        fontSize: '11px', color: '#aaa', marginTop: '2px',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                      }}>
                        {e.notes}
                      </div>
                    )}
                  </div>

                  {/* Days badge */}
                  <div style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    color: urgencyColor(e.days),
                    flexShrink: 0,
                    textAlign: 'right',
                  }}>
                    {urgencyLabel(e.days)}
                  </div>

                  {/* Link */}
                  {e.url && (
                    <a
                      href={e.url}
                      target="_blank"
                      rel="noreferrer"
                      style={{ fontSize: '14px', color: '#1a237e', flexShrink: 0 }}
                      title="Open auction site"
                    >
                      ↗
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
