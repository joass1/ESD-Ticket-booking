const BASE_URL = 'http://localhost:8000';

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
  return json.data !== undefined ? json.data : json;
}
