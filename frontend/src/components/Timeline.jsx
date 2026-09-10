import { useState } from "react";
import { Line } from "react-chartjs-2";

import { ACCENT, baseOptions } from "../charts.js";
import { fmtDate, fmtDateShort, fmtDateTime, fmtDuration, fmtInt, fmtMonth, mondayOf, weekdayOf } from "../format.js";
import { Empty, Section } from "./ui.jsx";

const UNITS = { day: "дни", week: "недели", month: "месяцы" };

// Бэкенд отдаёт сообщения по дням (с нулями для пустых дней); недели и месяцы
// собираем здесь — на длинных чатах дневной график превращается в шум.
function aggregate(dates, counts, unit) {
  if (unit === "day") return { labels: dates.map(fmtDateShort), values: counts };
  const buckets = new Map();
  dates.forEach((date, i) => {
    const key = unit === "month" ? date.slice(0, 7) : mondayOf(date);
    buckets.set(key, (buckets.get(key) ?? 0) + counts[i]);
  });
  const keys = [...buckets.keys()];
  return {
    labels: keys.map((k) => (unit === "month" ? fmtMonth(k) : `с ${fmtDateShort(k)}`)),
    values: keys.map((k) => buckets.get(k)),
  };
}

const defaultUnit = (days) => (days <= 120 ? "day" : days <= 730 ? "week" : "month");

export default function Timeline({ timeline }) {
  const [unit, setUnit] = useState(() => defaultUnit(timeline.dates.length));
  const { labels, values } = aggregate(timeline.dates, timeline.counts, unit);
  const peak = timeline.most_active_day;

  const data = {
    labels,
    datasets: [
      {
        data: values,
        borderColor: ACCENT,
        backgroundColor: `${ACCENT}22`,
        fill: true,
        cubicInterpolationMode: "monotone", // сглаживает, но не уводит линию ниже нуля
        pointRadius: values.length > 60 ? 0 : 2,
        borderWidth: 2,
      },
    ],
  };
  const options = {
    ...baseOptions,
    interaction: { mode: "index", intersect: false },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 10, maxRotation: 0, autoSkip: true } },
      y: { beginAtZero: true, ticks: { precision: 0 } },
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => ` ${fmtInt(ctx.raw)} сообщ.` } },
    },
  };

  return (
    <Section title="Таймлайн" subtitle="Сообщения по времени" className="timeline">
      <div className="segmented" role="group" aria-label="Шаг графика">
        {Object.entries(UNITS).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={unit === key ? "active" : ""}
            aria-pressed={unit === key}
            onClick={() => setUnit(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {timeline.dates.length > 1 ? (
        <div className="chart tall">
          <Line data={data} options={options} />
        </div>
      ) : (
        <Empty>Вся переписка уместилась в один день — {fmtDate(peak.date)}.</Empty>
      )}

      <div className="grid-2 facts">
        <div>
          <h3>Самый активный день</h3>
          <p className="big">
            {fmtDate(peak.date)} <span className="muted">({weekdayOf(peak.date)})</span>
          </p>
          <p className="muted">{fmtInt(peak.count)} сообщ.</p>
        </div>
        <div>
          <h3>Самые долгие тишины</h3>
          {timeline.longest_silences.length ? (
            <ol className="silences">
              {timeline.longest_silences.map((s) => (
                <li key={s.start}>
                  <strong>{fmtDuration(s.duration_s)}</strong>
                  <span className="muted">
                    {" "}
                    {fmtDateTime(s.start)} → {fmtDateTime(s.end)}, первым написал(а) {s.broken_by}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">Пауз между сообщениями нет.</p>
          )}
        </div>
      </div>
    </Section>
  );
}
