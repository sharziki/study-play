/* Transport. The only place that knows about HTTP. */

async function request(path, options) {
  const response = await fetch(path, options);
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_) {
    throw new Error("the server sent something unreadable");
  }
  if (!response.ok) throw new Error(data.error || `request failed (${response.status})`);
  return data;
}

export const api = {
  get(path) {
    return request(path, { headers: { Accept: "application/json" } });
  },
  post(path, body) {
    return request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  },
  query(path, params) {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== "" && value !== "All") {
        search.set(key, String(value));
      }
    });
    const suffix = search.toString();
    return this.get(suffix ? `${path}?${suffix}` : path);
  },
};
