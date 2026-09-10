// Клиент бэкенда. Адрес задаётся при сборке через VITE_API_URL
// (по умолчанию — локальный FastAPI на :8000).
const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

function errorText(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  // ошибки валидации FastAPI приходят списком
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  return `Ошибка сервера (${status})`;
}

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new Error(`Не удалось связаться с бэкендом (${API_URL}). Он запущен?`);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorText(body, response.status));
  return body;
}

export function fetchHealth() {
  return request("/api/health");
}

/** Отправляет файл на анализ. Файл уходит только на наш бэкенд и там не сохраняется. */
export function analyzeChat(file, { gapHours } = {}) {
  const body = new FormData();
  body.append("file", file);
  const query = gapHours ? `?gap_hours=${encodeURIComponent(gapHours)}` : "";
  return request(`/api/analyze${query}`, { method: "POST", body });
}
