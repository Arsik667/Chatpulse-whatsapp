// Форматирование чисел, дат и длительностей — те же правила, что в report_cli.py.

export const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

const numberFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
/** 12 345 · 2,56 — по-русски: пробел между разрядами и запятая в дробях */
export const fmtNum = (n) => numberFormat.format(n);
export const fmtInt = fmtNum;
export const fmtPct = (n) => `${fmtNum(n)}%`;

/** 1 сообщение · 2 сообщения · 5 сообщений */
export function plural(n, [one, few, many]) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

/** 45 с · 3 мин · 1 ч 5 мин · 2 дн 3 ч */
export function fmtDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  let s = Math.round(seconds);
  if (s < 60) return `${s} с`;
  let m = Math.floor(s / 60);
  s %= 60;
  if (m < 60) return `${m} мин${s && m < 10 ? ` ${s} с` : ""}`;
  let h = Math.floor(m / 60);
  m %= 60;
  if (h < 24) return `${h} ч${m ? ` ${m} мин` : ""}`;
  const d = Math.floor(h / 24);
  h %= 24;
  return `${d} дн${h ? ` ${h} ч` : ""}`;
}

// Даты из API — ISO-строки без часового пояса («время как в чате»).
// Режем строку, а не парсим через new Date(): «2025-09-01» браузер считает
// полночью по UTC и в западных поясах показал бы 31 августа.
export function fmtDate(iso) {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

export const fmtDateShort = (iso) => fmtDate(iso).replace(/\.(\d\d)(\d\d)$/, ".$2");

export const fmtDateTime = (iso) => `${fmtDate(iso)} ${iso.slice(11, 16)}`;

export function fmtMonth(yearMonth) {
  const [y, m] = yearMonth.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

/** Понедельник недели, в которую попадает дата (ISO → ISO). */
export function mondayOf(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
}

export function weekdayOf(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return WEEKDAYS[(new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7];
}
