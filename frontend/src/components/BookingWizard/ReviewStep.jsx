import { useState } from 'react';
import { CalendarDays, MapPin, Armchair, Tag, Phone } from 'lucide-react';

export default function ReviewStep({ event, seat, section, onConfirm, onBack }) {
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');

  const eventDate = event?.event_date
    ? new Date(event.event_date).toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email.trim() || !phone.trim()) return;
    onConfirm(email.trim(), phone.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-lg mx-auto">
      <h2 className="text-xl font-bold text-text-primary text-center">Review Your Booking</h2>

      <div className="bg-bg-card rounded-xl border border-white/10 p-6 space-y-4">
        <h3 className="text-lg font-semibold text-text-primary">{event?.name}</h3>

        <div className="space-y-2 text-sm text-text-secondary">
          {eventDate && (
            <div className="flex items-center gap-2">
              <CalendarDays size={14} className="text-accent" />
              {eventDate}
            </div>
          )}
          {event?.venue && (
            <div className="flex items-center gap-2">
              <MapPin size={14} className="text-accent" />
              {event.venue}
            </div>
          )}
        </div>

        <hr className="border-white/10" />

        <div className="space-y-2 text-sm">
          <div className="flex justify-between text-text-secondary">
            <span className="flex items-center gap-2">
              <Tag size={14} className="text-accent" />
              Section
            </span>
            <span className="text-text-primary font-medium">{section?.name || 'N/A'}</span>
          </div>
          <div className="flex justify-between text-text-secondary">
            <span className="flex items-center gap-2">
              <Armchair size={14} className="text-accent" />
              Seat
            </span>
            <span className="text-text-primary font-medium">
              Row {seat?.row_label}, Seat {seat?.seat_number}
            </span>
          </div>
          <div className="flex justify-between text-text-secondary">
            <span>Price</span>
            <span className="text-accent font-bold text-lg">
              ${Number(seat?.price || 0).toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* Contact details */}
      <div className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="email" className="block text-sm font-medium text-text-secondary">
            Email for e-ticket delivery
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full px-4 py-3 bg-bg-card border border-white/10 rounded-lg text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="phone" className="block text-sm font-medium text-text-secondary">
            Phone number for SMS notifications
          </label>
          <input
            id="phone"
            type="tel"
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+65 9123 4567"
            className="w-full px-4 py-3 bg-bg-card border border-white/10 rounded-lg text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <button
          type="submit"
          className="w-full py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors"
        >
          Proceed to Payment
        </button>
        <button
          type="button"
          onClick={onBack}
          className="w-full py-3 bg-white/5 hover:bg-white/10 text-text-secondary rounded-lg text-sm transition-colors"
        >
          Back to Seat Selection
        </button>
      </div>
    </form>
  );
}
