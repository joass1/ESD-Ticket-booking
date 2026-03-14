import { useEffect, useState } from 'react';
import { ArrowLeft, Check } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client.js';
import LoadingSpinner from '../ui/LoadingSpinner.jsx';

const STATUS_COLORS = {
  available: '#00b894',
  reserved: '#e17055',
  booked: '#e17055',
  selected: '#ffd700',
};

export default function SectionGrid({ eventId, section, onBack }) {
  const [seats, setSeats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSeat, setSelectedSeat] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchSeats = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api(`/api/seats/event/${eventId}`);
        const all = Array.isArray(data) ? data : [];
        setSeats(all.filter((s) => s.section_id === section.section_id));
      } catch (err) {
        setError(err.message || 'Failed to load seats');
      } finally {
        setLoading(false);
      }
    };
    fetchSeats();
  }, [eventId, section.section_id]);

  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-seat-taken text-center py-8">{error}</p>;

  // Normalize seats: extract display number from seat_number like "VIP-001"
  const normalized = seats.map((seat) => {
    const parts = String(seat.seat_number).split('-');
    const num = parts.length > 1 ? parseInt(parts[1], 10) : parseInt(parts[0], 10) || 0;
    return { ...seat, _num: num, price: seat.section_price ?? seat.price };
  });

  // Group into rows of 10
  const sorted = [...normalized].sort((a, b) => a._num - b._num);
  const rows = {};
  sorted.forEach((seat, idx) => {
    const rowLabel = String.fromCharCode(65 + Math.floor(idx / 10)); // A, B, C...
    if (!rows[rowLabel]) rows[rowLabel] = [];
    rows[rowLabel].push({ ...seat, row_label: rowLabel, display_num: (idx % 10) + 1 });
  });

  const sortedRowKeys = Object.keys(rows).sort();

  const handleSeatClick = (seat) => {
    if (seat.status !== 'available') return;
    setSelectedSeat((prev) => (prev?.seat_id === seat.seat_id ? null : seat));
  };

  const handleBookNow = () => {
    if (!selectedSeat) return;
    navigate(
      `/events/${eventId}/book?seatId=${selectedSeat.seat_id}&sectionId=${section.section_id}`
    );
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={16} />
          Back to Sections
        </button>
        <h3 className="text-lg font-semibold text-text-primary">
          {section.name} &mdash; ${Number(section.price).toFixed(2)}
        </h3>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mb-4">
        {[
          { label: 'Available', color: STATUS_COLORS.available },
          { label: 'Taken', color: STATUS_COLORS.reserved },
          { label: 'Selected', color: STATUS_COLORS.selected },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1.5 text-xs text-text-secondary">
            <span className="w-4 h-4 rounded-sm" style={{ backgroundColor: color }} />
            {label}
          </div>
        ))}
      </div>

      {/* Seat grid */}
      <div className="bg-bg-card rounded-xl p-4 border border-white/10">
        {/* Mini stage indicator */}
        <div className="mx-auto mb-4 w-1/2 h-6 rounded-b-xl bg-white/5 border border-white/10 flex items-center justify-center">
          <span className="text-[10px] text-text-secondary uppercase tracking-wider">Stage</span>
        </div>

        <div className="space-y-2">
          {sortedRowKeys.map((rowKey) => (
            <div key={rowKey} className="flex items-center gap-2">
              <span className="w-6 text-right text-xs text-text-secondary font-mono">
                {rowKey}
              </span>
              <div className="flex gap-1.5 flex-wrap">
                {rows[rowKey].map((seat) => {
                  const isSelected = selectedSeat?.seat_id === seat.seat_id;
                  const isAvailable = seat.status === 'available';
                  const color = isSelected
                    ? STATUS_COLORS.selected
                    : STATUS_COLORS[seat.status] || STATUS_COLORS.reserved;

                  return (
                    <button
                      key={seat.seat_id}
                      onClick={() => handleSeatClick(seat)}
                      disabled={!isAvailable && !isSelected}
                      title={`Row ${seat.row_label} Seat ${seat.display_num} - ${seat.status}`}
                      className="w-8 h-8 rounded-md flex items-center justify-center text-[10px] font-bold transition-all focus:outline-none focus:ring-2 focus:ring-accent"
                      style={{
                        backgroundColor: color,
                        opacity: isAvailable || isSelected ? 1 : 0.4,
                        cursor: isAvailable || isSelected ? 'pointer' : 'not-allowed',
                      }}
                    >
                      {isSelected ? <Check size={14} className="text-black" /> : seat.display_num}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Selection summary */}
      {selectedSeat && (
        <div className="mt-4 bg-bg-card rounded-xl p-4 border border-accent/30 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-sm text-text-primary">
            <span className="text-text-secondary">Selected: </span>
            <span className="font-semibold">
              Row {selectedSeat.row_label}, Seat {selectedSeat.display_num}
            </span>
            <span className="text-text-secondary"> &middot; {section.name} &middot; </span>
            <span className="font-semibold text-accent">
              ${Number(selectedSeat.price).toFixed(2)}
            </span>
          </div>
          <button
            onClick={handleBookNow}
            className="px-6 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors text-sm"
          >
            Book Now
          </button>
        </div>
      )}
    </div>
  );
}
