// Общие настройки Chart.js: регистрируем только нужные части (меньше бандл)
// и берём цвета осей из CSS-переменных, чтобы графики жили в светлой и тёмной теме.
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";

Chart.register(ArcElement, BarElement, CategoryScale, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip);

// Та же палитра, что в PDF-отчёте.
export const ACCENT = "#4F46E5";
export const ACCENT_2 = "#10B981";
export const MISSED = "#F59E0B";
export const PALETTE = [ACCENT, ACCENT_2, MISSED, "#EC4899", "#0EA5E9", "#8B5CF6", "#84CC16", "#64748B"];
export const REST_COLOR = "#9CA3AF";

export function applyChartTheme() {
  const css = getComputedStyle(document.documentElement);
  Chart.defaults.color = css.getPropertyValue("--muted").trim();
  Chart.defaults.borderColor = css.getPropertyValue("--border").trim();
  Chart.defaults.font.family = css.getPropertyValue("--font").trim();
}

// Числа на осях и в подсказках: «0,5» по-русски и «0.5» по-английски.
export function applyChartLocale(lang) {
  Chart.defaults.locale = lang === "ru" ? "ru-RU" : "en-US";
}

export const baseOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
};

/** Горизонтальный bar: подписи слева, значения по оси X. */
export const horizontalOptions = {
  ...baseOptions,
  indexAxis: "y",
  scales: { y: { grid: { display: false } } },
};
