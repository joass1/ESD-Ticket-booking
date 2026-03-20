import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Ticket, QrCode, AlertTriangle } from 'lucide-react';
import { api } from '../api/client.js';
import LoadingSpinner from '../components/ui/LoadingSpinner.jsx';

const STATUS_STYLES = {
  confirmed: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Confirmed' },
  pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Pending' },
  payment_pending: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Payment Pending' },
  pending_refund: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Refund Processing' },
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

function BookingCard({ booking, userId, onRefundSuccess }) {
  const [ticket, setTicket] = useState(null);
  const [showTicket, setShowTicket] = useState(false);
  const [ticketLoading, setTicketLoading] = useState(false);
  const [refundInfo, setRefundInfo] = useState(null);
  const [showRefundModal, setShowRefundModal] = useState(false);
  const [refundLoading, setRefundLoading] = useState(false);
  const [refundError, setRefundError] = useState(null);

  const fetchRefundInfo = async () => {
    if (refundInfo) return;
    try {
      const data = await api(`/api/charging/booking/${booking.booking_id}`);
      setRefundInfo(data);
    } catch {
      setRefundInfo(null);
    }
  };

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

  const handleRefund = async () => {
    setRefundLoading(true);
    setRefundError(null);
    try {
      await api(`/api/orchestrator/bookings/${booking.booking_id}/refund`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      });
      setShowRefundModal(false);
      onRefundSuccess(booking.booking_id);
    } catch (err) {
      setRefundError(err.message || 'Refund request failed');
    } finally {
      setRefundLoading(false);
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

  const amount = Number(booking.amount);
  const estimatedFee = Math.round(amount * 0.10 * 100) / 100;
  const estimatedRefund = Math.round((amount - estimatedFee) * 100) / 100;

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
            ${amount.toFixed(2)}
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
        <div className="flex items-center gap-3">
          <button
            onClick={handleViewTicket}
            disabled={ticketLoading}
            className="flex items-center gap-1.5 text-sm text-accent hover:text-accent-hover transition-colors"
          >
            <QrCode size={14} />
            {ticketLoading ? 'Loading...' : showTicket ? 'Hide Ticket' : 'View Ticket'}
          </button>
          <button
            onClick={() => setShowRefundModal(true)}
            className="flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300 transition-colors"
          >
            Request Refund
          </button>
        </div>
      )}

      {showTicket && ticket && (
        <div className="bg-bg-primary rounded-lg p-4 border border-white/10 text-center space-y-2">
          {ticket.qr_code_base64 ? (
            <img
              src={`data:image/png;base64,${ticket.qr_code_base64}`}
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

      {(booking.status === 'refunded' || booking.status === 'pending_refund') && !refundInfo && (
        <button
          onClick={fetchRefundInfo}
          className="w-full text-sm text-primary hover:text-primary/80 transition-colors py-2"
        >
          View Refund Details
        </button>
      )}

      {(booking.status === 'refunded' || booking.status === 'pending_refund') && refundInfo && (
        <div className="bg-bg-primary rounded-lg p-4 border border-white/10 space-y-2">
          <p className="text-sm font-medium text-text-primary">Refund Breakdown</p>
          {Number(refundInfo.service_fee) === 0 ? (
            <div className="text-sm">
              <div>
                <p className="text-text-secondary text-xs">Full Refund</p>
                <p className="text-green-400 font-semibold">${Number(refundInfo.refund_amount).toFixed(2)}</p>
              </div>
              <p className="text-xs text-text-secondary mt-2">
                No service fee — event was cancelled by the organizer.
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <p className="text-text-secondary">Original</p>
                  <p className="text-text-primary font-semibold">${Number(refundInfo.original_amount).toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-text-secondary">Service Fee (10%)</p>
                  <p className="text-red-400 font-semibold">-${Number(refundInfo.service_fee).toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-text-secondary">Refunded</p>
                  <p className="text-green-400 font-semibold">${Number(refundInfo.refund_amount).toFixed(2)}</p>
                </div>
              </div>
              <p className="text-xs text-text-secondary">
                {booking.status === 'refunded'
                  ? 'Refunded to your original payment method via Stripe.'
                  : 'Refund is being processed via Stripe.'}
              </p>
            </>
          )}
        </div>
      )}

      {/* Refund Confirmation Modal */}
      {showRefundModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-bg-card border border-white/10 rounded-xl p-6 max-w-md w-full mx-4 space-y-4">
            <div className="flex items-center gap-2 text-yellow-400">
              <AlertTriangle size={20} />
              <h3 className="text-lg font-semibold text-text-primary">Confirm Refund</h3>
            </div>
            <div className="space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <p className="text-text-secondary">Original Amount:</p>
                <p className="text-text-primary font-semibold">${amount.toFixed(2)}</p>
                <p className="text-text-secondary">Service Fee (10%):</p>
                <p className="text-red-400 font-semibold">-${estimatedFee.toFixed(2)}</p>
                <p className="text-text-secondary">You will receive:</p>
                <p className="text-green-400 font-semibold">${estimatedRefund.toFixed(2)}</p>
              </div>
            </div>
            <p className="text-xs text-yellow-400/80">
              This action cannot be undone. Your seat will be released and your ticket invalidated.
            </p>
            {refundError && (
              <p className="text-xs text-red-400">{refundError}</p>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => { setShowRefundModal(false); setRefundError(null); }}
                disabled={refundLoading}
                className="flex-1 px-4 py-2 rounded-lg border border-white/10 text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleRefund}
                disabled={refundLoading}
                className="flex-1 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors font-medium"
              >
                {refundLoading ? 'Processing...' : 'Confirm Refund'}
              </button>
            </div>
          </div>
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

  const handleRefundSuccess = (bookingId) => {
    setBookings((prev) =>
      prev.map((b) =>
        b.booking_id === bookingId ? { ...b, status: 'pending_refund' } : b
      )
    );
  };

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
            <BookingCard
              key={booking.booking_id}
              booking={booking}
              userId={userId}
              onRefundSuccess={handleRefundSuccess}
            />
          ))}
        </div>
      )}
    </div>
  );
}
