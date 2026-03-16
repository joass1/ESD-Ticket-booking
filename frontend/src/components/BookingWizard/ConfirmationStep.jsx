import { useEffect, useState } from 'react';
import { CheckCircle, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client.js';
import useSocket from '../../hooks/useSocket.js';

export default function ConfirmationStep({ bookingId, onViewBookings }) {
  const { ticketReady } = useSocket(bookingId);
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!bookingId) return;

    let cancelled = false;
    let intervalId = null;

    const fetchTicket = async () => {
      try {
        const data = await api(`/api/tickets/booking/${bookingId}`);
        if (!cancelled) {
          setTicket(data);
          setError(null);
          setLoading(false);
          // Stop polling once ticket is found
          if (intervalId) clearInterval(intervalId);
        }
      } catch {
        if (!cancelled) {
          setError('Could not load ticket yet');
          setLoading(false);
        }
      }
    };

    // When WebSocket says ticket is ready, fetch immediately
    if (ticketReady) {
      fetchTicket();
      return () => { cancelled = true; };
    }

    // Fallback: poll every 3 seconds for up to 30 seconds
    const timer = setTimeout(fetchTicket, 2000);
    intervalId = setInterval(fetchTicket, 3000);
    const stopPolling = setTimeout(() => {
      if (intervalId) clearInterval(intervalId);
    }, 30000);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      clearTimeout(stopPolling);
      if (intervalId) clearInterval(intervalId);
    };
  }, [bookingId, ticketReady]);

  return (
    <div className="max-w-lg mx-auto text-center space-y-6">
      <div className="flex justify-center">
        <CheckCircle size={64} className="text-seat-available" />
      </div>

      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-text-primary">Booking Confirmed!</h2>
        <p className="text-text-secondary text-sm">
          Booking ID: <span className="font-mono text-text-primary">{bookingId}</span>
        </p>
      </div>

      {/* QR Code */}
      <div className="bg-bg-card rounded-xl border border-white/10 p-6">
        {loading ? (
          <div className="flex flex-col items-center gap-3 py-8">
            <Loader2 size={32} className="animate-spin text-accent" />
            <p className="text-text-secondary text-sm">Loading your e-ticket...</p>
          </div>
        ) : ticket?.qr_code_base64 ? (
          <div className="space-y-4">
            <p className="text-sm text-text-secondary">Your E-Ticket</p>
            <img
              src={`data:image/png;base64,${ticket.qr_code_base64}`}
              alt="E-Ticket QR Code"
              className="w-48 h-48 mx-auto rounded-lg"
            />
            <p className="text-xs text-text-secondary">
              Scan this QR code at the venue entrance
            </p>
          </div>
        ) : error ? (
          <div className="py-8">
            <p className="text-text-secondary text-sm">{error}</p>
            <p className="text-text-secondary text-xs mt-2">
              Your ticket will be available in your bookings shortly.
            </p>
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-3">
        <Link
          to="/bookings"
          onClick={onViewBookings}
          className="w-full py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors inline-block"
        >
          View My Bookings
        </Link>
        <Link
          to="/"
          className="w-full py-3 bg-white/5 hover:bg-white/10 text-text-secondary rounded-lg text-sm transition-colors inline-block"
        >
          Back to Events
        </Link>
      </div>
    </div>
  );
}
