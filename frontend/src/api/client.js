const BASE_URL = 'http://localhost:8000';

// Override images for specific events with more relevant photos
const IMAGE_OVERRIDES = {
  20: 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800', // Ed Sheeran — guitar performer on stage
  24: 'https://images.unsplash.com/photo-1540039155733-5bb30b53aa14?w=800', // Blackpink — pink-lit concert stage
  25: 'https://images.unsplash.com/photo-1742744652734-d5ec6598b5da?w=800', // Singapore GP — F1 race car on track
};

/**
 * Normalize an OutSystems Event object (PascalCase) to the
 * snake_case format the frontend components expect.
 */
function normalizeEvent(e) {
  if (!e || typeof e !== 'object') return e;
  return {
    event_id:       e.Id          ?? e.event_id,
    name:           e.Name        ?? e.name,
    description:    e.Description ?? e.description,
    category:       e.Category    ?? e.category,
    event_date:     e.EventDate   ?? e.event_date,
    start_datetime: e.EventDate   ?? e.start_datetime ?? e.event_date,
    venue:          e.Venue       ?? e.venue,
    status:         e.Status      ?? e.status ?? 'upcoming',
    total_seats:    e.TotalSeats  ?? e.total_seats,
    available_seats:e.AvailableSeats ?? e.available_seats,
    min_price:      e.PriceMin    ?? e.min_price,
    max_price:      e.PriceMax    ?? e.max_price,
    image_url:      IMAGE_OVERRIDES[e.Id ?? e.event_id] ?? e.ImageUrl ?? e.image_url,
    created_at:     e.CreatedAt   ?? e.created_at,
    updated_at:     e.UpdatedAt   ?? e.updated_at,
  };
}

export async function api(path, options = {}) {
  const correlationId = crypto.randomUUID();

  const headers = {
    'Content-Type': 'application/json',
    'X-Correlation-ID': correlationId,
    ...options.headers,
  };

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const error = new Error(errorBody.message || `API error: ${response.status}`);
    error.status = response.status;
    error.correlationId = correlationId;
    throw error;
  }

  const json = await response.json();
  let data = json.data !== undefined ? json.data : json;

  // Normalize OutSystems PascalCase event responses to snake_case
  if (path.startsWith('/api/events') || path.startsWith('/api/event')) {
    data = Array.isArray(data) ? data.map(normalizeEvent) : normalizeEvent(data);
  }

  return data;
}
