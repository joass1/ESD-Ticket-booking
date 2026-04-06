import { useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { Plus, Trash2, CalendarDays, MapPin, Tag, AlignLeft, Image, Users } from 'lucide-react';
import { api } from '../api/client.js';

const EMPTY_SECTION = { name: '', price: '', seats: '' };

export default function CreateEventPage() {
  const navigate = useNavigate();
  const { userId } = useOutletContext();
  const isAdmin = userId === 'admin';

  const [form, setForm] = useState({
    name: '',
    description: '',
    category: 'Concert',
    event_date: '',
    venue: '',
    image_url: '',
  });

  const [sections, setSections] = useState([
    { name: 'VIP', price: '388', seats: '30' },
    { name: 'CAT1', price: '248', seats: '50' },
    { name: 'CAT2', price: '88', seats: '50' },
  ]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isAdmin) {
    return (
      <div className="text-center py-12">
        <p className="text-seat-taken">Only admins can create events.</p>
      </div>
    );
  }

  const updateField = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  const updateSection = (idx, field, value) => {
    setSections((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));
  };

  const addSection = () => setSections((prev) => [...prev, { ...EMPTY_SECTION }]);

  const removeSection = (idx) => {
    if (sections.length <= 1) return;
    setSections((prev) => prev.filter((_, i) => i !== idx));
  };

  const totalSeats = sections.reduce((sum, s) => sum + (parseInt(s.seats) || 0), 0);
  const prices = sections.map((s) => parseFloat(s.price) || 0).filter((p) => p > 0);
  const minPrice = prices.length ? Math.min(...prices) : 0;
  const maxPrice = prices.length ? Math.max(...prices) : 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!form.name || !form.event_date || !form.venue) {
      setError('Name, date, and venue are required.');
      return;
    }

    const validSections = sections.filter((s) => s.name && s.price && s.seats);
    if (validSections.length === 0) {
      setError('At least one section with name, price, and seat count is required.');
      return;
    }

    setSubmitting(true);
    try {
      const result = await api('/api/orchestrator/events/create', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name,
          description: form.description,
          category: form.category,
          event_date: form.event_date,
          venue: form.venue,
          image_url: form.image_url,
          total_seats: totalSeats,
          price_min: minPrice,
          price_max: maxPrice,
          sections: validSections.map((s) => ({
            name: s.name,
            price: parseFloat(s.price),
            total_seats: parseInt(s.seats),
          })),
        }),
      });
      navigate(`/events/${result.event_id}`);
    } catch (err) {
      setError(err.message || 'Failed to create event');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold text-text-primary">Create Event</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Event details */}
        <div className="bg-bg-card rounded-xl border border-white/10 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">Event Details</h2>

          <div>
            <label className="flex items-center gap-2 text-sm text-text-secondary mb-1">
              <Tag size={14} /> Event Name
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="e.g. Taylor Swift: The Eras Tour"
              className="w-full px-4 py-2 bg-bg-primary text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
              required
            />
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm text-text-secondary mb-1">
              <AlignLeft size={14} /> Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) => updateField('description', e.target.value)}
              placeholder="Describe the event..."
              rows={3}
              className="w-full px-4 py-2 bg-bg-primary text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="flex items-center gap-2 text-sm text-text-secondary mb-1">
                <Tag size={14} /> Category
              </label>
              <select
                value={form.category}
                onChange={(e) => updateField('category', e.target.value)}
                className="w-full px-4 py-2 bg-bg-primary text-text-primary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
              >
                <option value="Concert">Concert</option>
                <option value="Sports">Sports</option>
                <option value="Theatre">Theatre</option>
                <option value="Festival">Festival</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div>
              <label className="flex items-center gap-2 text-sm text-text-secondary mb-1">
                <CalendarDays size={14} /> Date & Time
              </label>
              <input
                type="datetime-local"
                value={form.event_date}
                onChange={(e) => updateField('event_date', e.target.value)}
                className="w-full px-4 py-2 bg-bg-primary text-text-primary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
                required
              />
            </div>
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm text-text-secondary mb-1">
              <MapPin size={14} /> Venue
            </label>
            <input
              type="text"
              value={form.venue}
              onChange={(e) => updateField('venue', e.target.value)}
              placeholder="e.g. National Stadium, Singapore"
              className="w-full px-4 py-2 bg-bg-primary text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
              required
            />
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm text-text-secondary mb-1">
              <Image size={14} /> Image URL (optional)
            </label>
            <input
              type="url"
              value={form.image_url}
              onChange={(e) => updateField('image_url', e.target.value)}
              placeholder="https://images.unsplash.com/..."
              className="w-full px-4 py-2 bg-bg-primary text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
            />
          </div>
        </div>

        {/* Sections */}
        <div className="bg-bg-card rounded-xl border border-white/10 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
              <Users size={18} /> Seating Sections
            </h2>
            <span className="text-sm text-text-secondary">
              Total: {totalSeats} seats | ${minPrice.toFixed(2)} – ${maxPrice.toFixed(2)}
            </span>
          </div>

          {sections.map((section, idx) => (
            <div key={idx} className="flex items-end gap-3">
              <div className="flex-1">
                {idx === 0 && <label className="text-xs text-text-secondary mb-1 block">Name</label>}
                <input
                  type="text"
                  value={section.name}
                  onChange={(e) => updateSection(idx, 'name', e.target.value)}
                  placeholder="VIP"
                  className="w-full px-3 py-2 bg-bg-primary text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
                />
              </div>
              <div className="w-28">
                {idx === 0 && <label className="text-xs text-text-secondary mb-1 block">Price ($)</label>}
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={section.price}
                  onChange={(e) => updateSection(idx, 'price', e.target.value)}
                  placeholder="388"
                  className="w-full px-3 py-2 bg-bg-primary text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
                />
              </div>
              <div className="w-24">
                {idx === 0 && <label className="text-xs text-text-secondary mb-1 block">Seats</label>}
                <input
                  type="number"
                  min="1"
                  value={section.seats}
                  onChange={(e) => updateSection(idx, 'seats', e.target.value)}
                  placeholder="30"
                  className="w-full px-3 py-2 bg-bg-primary text-text-primary placeholder-text-secondary rounded-lg border border-white/10 focus:outline-none focus:ring-1 focus:ring-accent text-sm"
                />
              </div>
              <button
                type="button"
                onClick={() => removeSection(idx)}
                disabled={sections.length <= 1}
                className="p-2 text-text-secondary hover:text-seat-taken disabled:opacity-30 transition-colors"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}

          <button
            type="button"
            onClick={addSection}
            className="flex items-center gap-2 text-sm text-accent hover:text-accent-hover transition-colors"
          >
            <Plus size={14} /> Add Section
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-3 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-xl font-semibold transition-colors"
        >
          {submitting ? 'Creating Event...' : 'Create Event'}
        </button>
      </form>
    </div>
  );
}
