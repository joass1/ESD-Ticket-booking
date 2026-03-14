import { Link } from 'react-router-dom';
import { MapPin, CalendarDays } from 'lucide-react';

const statusColors = {
  upcoming: 'bg-seat-available/20 text-seat-available',
  ongoing: 'bg-yellow-500/20 text-yellow-400',
  cancelled: 'bg-seat-taken/20 text-seat-taken',
};

export default function EventCard({ event }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const statusClass = statusColors[event.status] || statusColors.upcoming;

  return (
    <Link
      to={`/events/${event.event_id}`}
      className="block bg-bg-card rounded-xl overflow-hidden hover:scale-[1.02] hover:ring-1 hover:ring-accent transition-all duration-200"
    >
      {event.image_url ? (
        <img
          src={event.image_url}
          alt={event.name}
          className="w-full h-48 object-cover"
        />
      ) : (
        <div className="w-full h-48 bg-gradient-to-br from-accent/40 to-bg-primary flex items-center justify-center">
          <span className="text-4xl text-text-secondary/50">
            {event.name?.[0] || '?'}
          </span>
        </div>
      )}

      <div className="p-4 space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-text-primary truncate">
            {event.name}
          </h3>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusClass}`}>
            {event.status}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-sm text-text-secondary">
          <CalendarDays size={14} />
          <span>{formatDate(event.start_datetime)}</span>
        </div>

        <div className="flex items-center gap-1.5 text-sm text-text-secondary">
          <MapPin size={14} />
          <span>{event.venue || 'TBA'}</span>
        </div>

        {event.min_price != null && (
          <p className="text-accent font-bold">
            From ${Number(event.min_price).toFixed(2)}
          </p>
        )}
      </div>
    </Link>
  );
}
