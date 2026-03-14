import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Ticket, QrCode } from 'lucide-react';
import { api } from '../api/client.js';
import LoadingSpinner from '../components/ui/LoadingSpinner.jsx';

const STATUS_STYLES = {
  confirmed: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Confirmed' },
  pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Pending' },
  payment_pending: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Payment Pending' },
  refunded: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'Refunded' },
  cancelled: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Cancelled' },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.pending;
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function BookingCard({ booking }) {
  const [ticket, setTicket] = useState(null);
  const [showTicket, setShowTicket] = useState(false);
  const [ticketLoading, setTicketLoading] = useState(false);

  const handleViewTicket = async () => {
    if (ticket) {
      setShowTicket(!showTicket);
      return;
    }
    setTicketLoading(true);
    try {
      const data = await api(`/api/tickets/booking/${booking.booking_id}`);
      setTicket(data);
      setShowTicket(true);
    } catch {
      // Ticket might not exist yet
      setTicket(null);
    } finally {
      setTicketLoading(false);
    }
  };

  const createdAt = booking.created_at
    ? new Date(booking.created_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  const shortId = booking.booking_id
    ? String(booking.booking_id).slice(0, 8) + '...'
    : '';

  return (
    <div className="bg-bg-card rounded-xl border border-white/10 p-5 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-text-secondary">Booking</p>
          <p className="text-text-primary font-mono text-sm">{shortId}</p>
        </div>
        <StatusBadge status={booking.status} />
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-text-secondary text-xs">Event</p>
          <p className="text-text-primary">
            {booking.event_name || `Event #${booking.event_id}`}
          </p>
        </div>
        <div>
          <p className="text-text-secondary text-xs">Amount</p>
          <p className="text-text-primary font-semibold">
            ${Number(booking.amount).toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-text-secondary text-xs">Seat</p>
          <p className="text-text-primary">
            {booking.seat_id ? `Seat #${booking.seat_id}` : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-text-secondary text-xs">Date</p>
          <p className="text-text-primary">{createdAt}</p>
        </div>
      </div>

      {booking.status === 'confirmed' && (
        <button
          onClick={handleViewTicket}
          disabled={ticketLoading}
          className="flex items-center gap-1.5 text-sm text-accent hover:text-accent-hover transition-colors"
        >
          <QrCode size={14} />
          {ticketLoading ? 'Loading...' : showTicket ? 'Hide Ticket' : 'View Ticket'}
        </button>
      )}

      {showTicket && ticket && (
        <div className="bg-bg-primary rounded-lg p-4 border border-white/10 text-center space-y-2">
          {ticket.qr_code_url ? (
            <img
              src={ticket.qr_code_url}
              alt="Ticket QR Code"
              className="w-32 h-32 mx-auto"
            />
          ) : (
            <div className="w-32 h-32 mx-auto bg-white rounded-lg flex items-center justify-center">
              <QrCode size={64} className="text-black" />
            </div>
          )}
          <p className="text-xs text-text-secondary font-mono">
            {ticket.ticket_id || ticket.validation_hash || 'Ticket ID unavailable'}
          </p>
          <p className="text-xs text-text-secondary">
            Status: {ticket.status || 'valid'}
          </p>
        </div>
      )}
    </div>
  );
}

export default function BookingHistoryPage() {
  const { userId } = useOutletContext();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchBookings = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api(`/api/bookings/user/${userId}`);
        setBookings(Array.isArray(data) ? data : []);
      } catch (err) {
        setError(err.message || 'Failed to load bookings');
      } finally {
        setLoading(false);
      }
    };
    fetchBookings();
  }, [userId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Ticket size={24} className="text-accent" />
        <h1 className="text-3xl font-bold text-text-primary">My Bookings</h1>
      </div>

      {loading && <LoadingSpinner />}

      {error && (
        <div className="text-center py-12">
          <p className="text-seat-taken">{error}</p>
        </div>
      )}

      {!loading && !error && bookings.length === 0 && (
        <div className="text-center py-12">
          <Ticket size={48} className="mx-auto text-text-secondary/30 mb-4" />
          <p className="text-text-secondary">No bookings yet</p>
          <p className="text-text-secondary text-sm mt-1">
            Browse events and book a seat to get started.
          </p>
        </div>
      )}

      {!loading && !error && bookings.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {bookings.map((booking) => (
            <BookingCard key={booking.booking_id} booking={booking} />
          ))}
        </div>
      )}
    </div>
  );
}
