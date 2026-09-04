export function parseJsonObject(value: string) {
  if (!value.trim()) {
    return {};
  }
  const parsed = JSON.parse(value);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('JSON value must be an object.');
  }
  return parsed as Record<string, unknown>;
}

export function parseCsv(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}
