import { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import LoadingSpinner from '../ui/LoadingSpinner.jsx';

const TIER_COLORS = {
  VIP: { bg: '#6c5ce7', border: '#a29bfe', label: 'VIP' },
  CAT1: { bg: '#e17055', border: '#fab1a0', label: 'CAT 1' },
  CAT2: { bg: '#00b894', border: '#55efc4', label: 'CAT 2' },
};

function getTier(name) {
  const upper = (name || '').toUpperCase();
  if (upper.includes('VIP')) return 'VIP';
  if (upper.includes('CAT1') || upper.includes('CAT 1')) return 'CAT1';
  return 'CAT2';
}

// Spatial layout positions around the stage
const LAYOUT = {
  VIP: [
    { gridRow: '4', gridColumn: '2 / 4', label: 'Front Center' },
    { gridRow: '4', gridColumn: '1', label: 'Front Left' },
    { gridRow: '4', gridColumn: '4', label: 'Front Right' },
  ],
  CAT1: [
    { gridRow: '2 / 5', gridColumn: '1', label: 'Left' },
    { gridRow: '2 / 5', gridColumn: '4', label: 'Right' },
  ],
  CAT2: [
    { gridRow: '1', gridColumn: '1 / 3', label: 'Back Left' },
    { gridRow: '1', gridColumn: '3 / 5', label: 'Back Right' },
  ],
};

export default function VenueOverview({ eventId, onSectionSelect, onSoldOutClick }) {
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSections = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api(`/api/seats/availability/${eventId}`);
        const list = data?.sections || (Array.isArray(data) ? data : []);
        setSections(list);
      } catch (err) {
        setError(err.message || 'Failed to load seat availability');
      } finally {
        setLoading(false);
      }
    };
    fetchSections();
  }, [eventId]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-seat-taken text-center py-8">{error}</p>;

  // Group sections by tier
  const grouped = { VIP: [], CAT1: [], CAT2: [] };
  sections.forEach((s) => {
    const tier = getTier(s.name);
    grouped[tier].push(s);
  });

  // Build positioned section blocks
  const blocks = [];
  Object.entries(grouped).forEach(([tier, secs]) => {
    const positions = LAYOUT[tier] || [];
    secs.forEach((section, idx) => {
      const pos = positions[idx % positions.length] || positions[0];
      blocks.push({ section, tier, pos });
    });
  });

  return (
    <div className="w-full max-w-3xl mx-auto">
      <h3 className="text-lg font-semibold text-text-primary mb-4 text-center">
        Select a Section
      </h3>

      {/* Legend */}
      <div className="flex justify-center gap-6 mb-6">
        {Object.entries(TIER_COLORS).map(([key, val]) => (
          <div key={key} className="flex items-center gap-2 text-sm text-text-secondary">
            <span
              className="w-4 h-4 rounded"
              style={{ backgroundColor: val.bg }}
            />
            {val.label}
          </div>
        ))}
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span className="w-4 h-4 rounded bg-gray-600 opacity-50" />
          Sold Out
        </div>
      </div>

      {/* Arena layout */}
      <div className="relative grid grid-cols-4 grid-rows-4 gap-3 p-4">
        {/* Stage */}
        <div
          className="col-start-2 col-end-4 row-start-2 row-end-4 flex items-center justify-center rounded-2xl border-2 border-white/20 bg-white/5"
        >
          <span className="text-text-secondary font-bold text-lg tracking-widest uppercase">
            Stage
          </span>
        </div>

        {/* Section blocks */}
        {blocks.map(({ section, tier, pos }) => {
          const soldOut = section.available_seats === 0;
          const colors = TIER_COLORS[tier];

          return (
            <button
              key={section.section_id}
              style={{
                gridRow: pos.gridRow,
                gridColumn: pos.gridColumn,
                backgroundColor: soldOut ? '#4b5563' : colors.bg,
                borderColor: soldOut ? '#6b7280' : colors.border,
                opacity: soldOut ? 0.5 : 1,
              }}
              className="relative rounded-xl border-2 p-3 min-h-[80px] flex flex-col items-center justify-center gap-1 transition-all cursor-pointer hover:brightness-125 focus:outline-none focus:ring-2 focus:ring-accent"
              onClick={() => {
                if (soldOut) {
                  onSoldOutClick?.(section);
                } else {
                  onSectionSelect?.(section);
                }
              }}
            >
              <span className="font-bold text-white text-sm">{section.name}</span>
              {soldOut ? (
                <>
                  <span className="text-xs text-white/80 font-medium">SOLD OUT</span>
                  <span className="text-[10px] text-white/60 mt-0.5">Join Waitlist</span>
                </>
              ) : (
                <>
                  <span className="text-xs text-white/80">
                    {section.available_seats} available
                  </span>
                  <span className="text-[10px] text-white/60">
                    ${Number(section.price).toFixed(2)}
                  </span>
                </>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
