import { useEffect, useMemo, useState } from 'react';
import { Search, SlidersHorizontal } from 'lucide-react';
import { api } from '../api/client.js';
import EventCard from '../components/EventCard.jsx';
import LoadingSpinner from '../components/ui/LoadingSpinner.jsx';

const STATUS_OPTIONS = ['All', 'upcoming', 'ongoing'];

export default function EventsPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All');

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api('/api/events');
      setEvents(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Failed to load events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEvents(); }, []);

  const categories = useMemo(() => {
    const cats = new Set(events.map((e) => e.category).filter(Boolean));
    return ['All', ...Array.from(cats).sort()];
  }, [events]);

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (search && !e.name?.toLowerCase().includes(search.toLowerCase())) return false;
      if (statusFilter !== 'All' && e.status !== statusFilter) return false;
      if (categoryFilter !== 'All' && e.category !== categoryFilter) return false;
      return true;
    });
  }, [events, search, statusFilter, categoryFilter]);

  const filterBtn = (label, active, onClick) => (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-accent text-white'
          : 'bg-white/5 text-text-secondary hover:text-text-primary hover:bg-white/10'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h1 className="text-3xl font-bold text-text-primary">Upcoming Events</h1>

        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            placeholder="Search events..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 w-full sm:w-64 bg-bg-card text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <SlidersHorizontal size={14} className="text-text-secondary" />
        <span className="text-xs text-text-secondary mr-1">Status:</span>
        {STATUS_OPTIONS.map((s) => filterBtn(s, statusFilter === s, () => setStatusFilter(s)))}

        <span className="text-xs text-text-secondary ml-4 mr-1">Category:</span>
        {categories.map((c) => filterBtn(c, categoryFilter === c, () => setCategoryFilter(c)))}
      </div>

      {loading && <LoadingSpinner />}

      {error && (
        <div className="text-center py-12 space-y-4">
          <p className="text-seat-taken">{error}</p>
          <button
            onClick={fetchEvents}
            className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors text-sm"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <p className="text-center text-text-secondary py-12">No events found</p>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((event) => (
            <EventCard key={event.event_id} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
