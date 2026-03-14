import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useOutletContext } from 'react-router-dom';
import { ArrowLeft, Clock, Users } from 'lucide-react';
import { api } from '../api/client.js';
import LoadingSpinner from '../components/ui/LoadingSpinner.jsx';

const POLL_INTERVAL = 10000; // 10 seconds

export default function WaitlistPage() {
  const { eventId } = useParams();
  const { userId } = useOutletContext();
  const [event, setEvent] = useState(null);
  const [sections, setSections] = useState([]);
  const [selectedSection, setSelectedSection] = useState('');
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState(null);
  const [position, setPosition] = useState(null);
  const [waitlistStatus, setWaitlistStatus] = useState(null);
  const pollRef = useRef(null);

  // Fetch event info and sections
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [eventData, sectionData] = await Promise.all([
          api(`/api/events/${eventId}`),
          api(`/api/seats/availability/${eventId}`),
        ]);
        setEvent(eventData);
        const secs = Array.isArray(sectionData) ? sectionData : [];
        setSections(secs);
        if (secs.length > 0) setSelectedSection(secs[0].name);
      } catch (err) {
        setError(err.message || 'Failed to load event data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [eventId]);

  // Poll for position
  const pollPosition = async () => {
    try {
      const data = await api(`/api/waitlist/position/${eventId}/${userId}`);
      setPosition(data.position);
      setWaitlistStatus(data.status);
    } catch {
      // User not on waitlist yet - ignore
    }
  };

  // Check existing waitlist position on load
  useEffect(() => {
    pollPosition();
  }, [eventId, userId]);

  // Start polling when on waitlist
  useEffect(() => {
    if (position !== null) {
      pollRef.current = setInterval(pollPosition, POLL_INTERVAL);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [position !== null]);

  const handleJoin = async () => {
    if (!selectedSection) return;
    setJoining(true);
    setError(null);
    try {
      await api('/api/waitlist/join', {
        method: 'POST',
        body: JSON.stringify({
          user_id: userId,
          event_id: Number(eventId),
          section_name: selectedSection,
        }),
      });
      // Immediately fetch position after joining
      await pollPosition();
    } catch (err) {
      if (err.status === 409) {
        // Already on waitlist
        await pollPosition();
      } else {
        setError(err.message || 'Failed to join waitlist');
      }
    } finally {
      setJoining(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="max-w-lg mx-auto space-y-6">
      {/* Back link */}
      <Link
        to={`/events/${eventId}`}
        className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Event
      </Link>

      {/* Event info */}
      {event && (
        <div className="bg-bg-card rounded-xl border border-white/10 p-5">
          <h1 className="text-2xl font-bold text-text-primary">{event.name}</h1>
          <p className="text-text-secondary text-sm mt-1">Waitlist</p>
        </div>
      )}

      {error && (
        <p className="text-seat-taken text-sm text-center">{error}</p>
      )}

      {/* Already on waitlist - show position */}
      {position !== null ? (
        <div className="bg-bg-card rounded-xl border border-white/10 p-6 text-center space-y-4">
          <div className="w-16 h-16 mx-auto rounded-full bg-accent/20 flex items-center justify-center">
            <Users size={28} className="text-accent" />
          </div>

          <div>
            <p className="text-text-secondary text-sm">Your position in queue</p>
            <p className="text-4xl font-bold text-accent mt-1">#{position}</p>
          </div>

          <div className="flex items-center justify-center gap-2 text-sm">
            <span
              className={`px-3 py-1 rounded-full font-medium ${
                waitlistStatus === 'promoted'
                  ? 'bg-green-500/20 text-green-400'
                  : waitlistStatus === 'expired'
                  ? 'bg-red-500/20 text-red-400'
                  : 'bg-yellow-500/20 text-yellow-400'
              }`}
            >
              {waitlistStatus === 'promoted'
                ? 'Promoted!'
                : waitlistStatus === 'expired'
                ? 'Expired'
                : 'Waiting'}
            </span>
          </div>

          {waitlistStatus === 'promoted' && (
            <Link
              to={`/events/${eventId}`}
              className="inline-block px-5 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
            >
              Complete Booking
            </Link>
          )}

          <div className="flex items-center justify-center gap-1 text-xs text-text-secondary">
            <Clock size={12} />
            Updates every 10 seconds
          </div>
        </div>
      ) : (
        /* Join waitlist form */
        <div className="bg-bg-card rounded-xl border border-white/10 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">Join Waitlist</h2>
          <p className="text-sm text-text-secondary">
            Select a section to join the waitlist. You will be notified when a seat becomes available.
          </p>

          <div>
            <label className="block text-sm text-text-secondary mb-1.5">Preferred Section</label>
            <select
              value={selectedSection}
              onChange={(e) => setSelectedSection(e.target.value)}
              className="w-full bg-bg-primary text-text-primary border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {sections.map((s) => (
                <option key={s.section_id} value={s.name}>
                  {s.name} — {s.available_seats} available — ${Number(s.price).toFixed(2)}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleJoin}
            disabled={joining || !selectedSection}
            className="w-full py-2.5 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-lg font-medium transition-colors text-sm"
          >
            {joining ? 'Joining...' : 'Join Waitlist'}
          </button>
        </div>
      )}
    </div>
  );
}
