import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CalendarDays, MapPin } from 'lucide-react';
import { api } from '../api/client.js';
import VenueOverview from '../components/SeatMap/VenueOverview.jsx';
import SectionGrid from '../components/SeatMap/SectionGrid.jsx';
import LoadingSpinner from '../components/ui/LoadingSpinner.jsx';

export default function EventDetailPage() {
  const { eventId } = useParams();
  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState('overview'); // 'overview' | 'section'
  const [selectedSection, setSelectedSection] = useState(null);
  const [waitlistPrompt, setWaitlistPrompt] = useState(null);

  useEffect(() => {
    const fetchEvent = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api(`/api/events/${eventId}`);
        setEvent(data);
      } catch (err) {
        setError(err.message || 'Failed to load event');
      } finally {
        setLoading(false);
      }
    };
    fetchEvent();
  }, [eventId]);

  const handleSectionSelect = (section) => {
    setSelectedSection(section);
    setView('section');
    setWaitlistPrompt(null);
  };

  const handleSoldOutClick = (section) => {
    setWaitlistPrompt(section);
  };

  const handleBackToOverview = () => {
    setView('overview');
    setSelectedSection(null);
    setWaitlistPrompt(null);
  };

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-seat-taken mb-4">{error}</p>
        <Link to="/" className="text-accent hover:underline text-sm">
          Back to Events
        </Link>
      </div>
    );
  }

  if (!event) return null;

  const eventDate = event.event_date
    ? new Date(event.event_date).toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  return (
    <div className="space-y-6">
      {/* Event banner */}
      <div className="relative rounded-2xl overflow-hidden bg-bg-card border border-white/10">
        {event.image_url && (
          <img
            src={event.image_url}
            alt={event.name}
            className="w-full h-56 object-cover opacity-80"
          />
        )}
        <div className="p-6">
          <h1 className="text-3xl font-bold text-text-primary">{event.name}</h1>
          <div className="flex flex-wrap gap-4 mt-3 text-sm text-text-secondary">
            {eventDate && (
              <span className="flex items-center gap-1.5">
                <CalendarDays size={14} />
                {eventDate}
              </span>
            )}
            {event.venue && (
              <span className="flex items-center gap-1.5">
                <MapPin size={14} />
                {event.venue}
              </span>
            )}
          </div>
          {event.status && (
            <span className="inline-block mt-3 px-3 py-1 rounded-full text-xs font-medium bg-accent/20 text-accent capitalize">
              {event.status}
            </span>
          )}
        </div>
      </div>

      {/* Waitlist prompt overlay */}
      {waitlistPrompt && (
        <div className="bg-bg-card rounded-xl border border-white/10 p-6 text-center space-y-3">
          <p className="text-text-primary font-medium">
            {waitlistPrompt.name} is sold out
          </p>
          <p className="text-text-secondary text-sm">
            Join the waitlist to be notified when seats become available.
          </p>
          <div className="flex justify-center gap-3">
            <Link
              to={`/events/${eventId}/waitlist`}
              className="px-5 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
            >
              Join Waitlist
            </Link>
            <button
              onClick={() => setWaitlistPrompt(null)}
              className="px-5 py-2 bg-white/5 hover:bg-white/10 text-text-secondary rounded-lg text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Seat map */}
      {view === 'overview' && (
        <VenueOverview
          eventId={eventId}
          onSectionSelect={handleSectionSelect}
          onSoldOutClick={handleSoldOutClick}
        />
      )}

      {view === 'section' && selectedSection && (
        <SectionGrid
          eventId={eventId}
          section={selectedSection}
          onBack={handleBackToOverview}
        />
      )}
    </div>
  );
}
