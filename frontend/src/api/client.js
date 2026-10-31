export async function api(path, body, method = body ? 'POST' : 'GET') {
  const response = await fetch(path, {
    method,
    ...(body ? {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {}),
  });
  const value = await response.json();
  if (!response.ok) {
    throw new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail || value.error));
  }
  return value;
}
