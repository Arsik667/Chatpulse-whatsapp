// Клиент бэкенда. Адрес задаётся при сборке через VITE_API_URL
// (по умолчанию — локальный FastAPI на :8000).
export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/**
 * code: "network" — бэкенд недоступен, "server" — ответ без текста ошибки,
 * "detail" — бэкенд сам прислал текст (уже на языке из ?lang=).
 * Первые два текста интерфейс переводит сам.
 */
export class ApiError extends Error {
  constructor(code, message = code, status = 0) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new ApiError("network");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    if (typeof detail === "string") throw new ApiError("detail", detail, response.status);
    // ошибки валидации FastAPI приходят списком
    if (Array.isArray(detail)) throw new ApiError("detail", detail.map((d) => d.msg).join("; "), response.status);
    throw new ApiError("server", `HTTP ${response.status}`, response.status);
  }
  return body;
}

export function fetchHealth() {
  return request("/api/health");
}

/** Отправляет файл на анализ. Файл уходит только на наш бэкенд и там не сохраняется. */
export function analyzeChat(file, { gapHours, lang } = {}) {
  const body = new FormData();
  body.append("file", file);
  const params = new URLSearchParams();
  if (gapHours) params.set("gap_hours", gapHours);
  if (lang) params.set("lang", lang);
  return request(`/api/analyze?${params}`, { method: "POST", body });
}
