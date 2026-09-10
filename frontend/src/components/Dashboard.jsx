import { Bar, Doughnut } from "react-chartjs-2";

import { ACCENT, ACCENT_2, MISSED, PALETTE, REST_COLOR, baseOptions, horizontalOptions } from "../charts.js";
import { WEEKDAYS, fmtDate, fmtDuration, fmtInt, fmtNum, fmtPct, plural } from "../format.js";
import Heatmap from "./Heatmap.jsx";
import Timeline from "./Timeline.jsx";
import { Empty, Kpi, Section } from "./ui.jsx";
import WordCloud from "./WordCloud.jsx";

const GAP_OPTIONS = [1, 3, 6, 12, 24];
const PLATFORMS = { android: "Android", ios: "iOS" };
const MAX_SLICES = 7; // в «пончике» больше кусков не читается — остальных объединяем

// --- шапка и ключевые цифры -----------------------------------------------------------

function Header({ meta, fileName, gapHours, onGapChange, loading }) {
  const period = meta.first_message
    ? `${fmtDate(meta.first_message)} – ${fmtDate(meta.last_message)} · ${meta.days} ${plural(meta.days, ["день", "дня", "дней"])}`
    : "нет сообщений";
  return (
    <div className="dash-header">
      <div>
        <h1>{fileName}</h1>
        <p className="subtitle">
          WhatsApp · {PLATFORMS[meta.platform]} · {period}
          {meta.participants.length > 0 && ` · ${meta.participants.join(", ")}`}
        </p>
      </div>
      <label className="gap-select">
        Новый разговор после паузы
        <select value={gapHours} onChange={(e) => onGapChange(Number(e.target.value))} disabled={loading}>
          {GAP_OPTIONS.map((h) => (
            <option key={h} value={h}>
              {h} ч
            </option>
          ))}
        </select>
        {loading && <span className="spinner small" aria-label="Пересчитываем" />}
      </label>
    </div>
  );
}

function Kpis({ summary, calls }) {
  return (
    <div className="kpis">
      <Kpi value={fmtInt(summary.messages)} label={plural(summary.messages, ["сообщение", "сообщения", "сообщений"])} />
      <Kpi value={fmtInt(summary.words)} label={plural(summary.words, ["слово", "слова", "слов"])} />
      <Kpi value={fmtInt(summary.media)} label="медиа" />
      <Kpi value={fmtInt(summary.links)} label={plural(summary.links, ["ссылка", "ссылки", "ссылок"])} />
      <Kpi value={fmtNum(summary.avg_words_per_message)} label="слов в сообщении" />
      <Kpi value={fmtInt(calls.total)} label={plural(calls.total, ["звонок", "звонка", "звонков"])} />
    </div>
  );
}

// --- участники --------------------------------------------------------------------------

function slices(people, key) {
  const sorted = [...people].sort((a, b) => b[key] - a[key]);
  if (sorted.length <= MAX_SLICES + 1) return sorted.map((p) => ({ name: p.name, value: p[key] }));
  const rest = sorted.slice(MAX_SLICES).reduce((sum, p) => sum + p[key], 0);
  return [...sorted.slice(0, MAX_SLICES).map((p) => ({ name: p.name, value: p[key] })), { name: "Остальные", value: rest }];
}

function ShareDoughnut({ data, colorOf, unit }) {
  const total = data.reduce((sum, d) => sum + d.value, 0) || 1;
  const pct = (value) => fmtPct(Math.round((1000 * value) / total) / 10);
  const chart = {
    // проценты прямо в легенде — чтобы не приходилось наводить мышь
    labels: data.map((d) => `${d.name} · ${pct(d.value)}`),
    datasets: [
      {
        data: data.map((d) => d.value),
        backgroundColor: data.map((d) => colorOf(d.name)),
        borderWidth: 0,
      },
    ],
  };
  const options = {
    ...baseOptions,
    cutout: "62%",
    plugins: {
      legend: { position: "right", labels: { boxWidth: 12, padding: 12 } },
      tooltip: {
        callbacks: {
          label: (ctx) => ` ${fmtInt(ctx.raw)} ${unit}`,
        },
      },
    },
  };
  return (
    <div className="chart">
      <Doughnut data={chart} options={options} />
    </div>
  );
}

function ParticipantsTable({ participants, responseTimes }) {
  const replies = Object.fromEntries(responseTimes.map((r) => [r.name, r]));
  const solo = participants.length < 2; // одному участнику «начинать разговор» не с кем
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Участник</th>
            <th>Сообщений</th>
            <th>Доля</th>
            <th>Слов</th>
            <th>Слов в сообщ.</th>
            <th>Медиа</th>
            <th>Ссылок</th>
            <th>Начинал разговор</th>
            <th>Ответ: медиана</th>
            <th>Ответ: среднее</th>
          </tr>
        </thead>
        <tbody>
          {participants.map((p) => (
            <tr key={p.name}>
              <td>{p.name}</td>
              <td>{fmtInt(p.messages)}</td>
              <td>{fmtPct(p.share)}</td>
              <td>{fmtInt(p.words)}</td>
              <td>{fmtNum(p.avg_words)}</td>
              <td>{fmtInt(p.media)}</td>
              <td>{fmtInt(p.links)}</td>
              <td>{solo ? "—" : `${fmtInt(p.initiations)} · ${fmtPct(p.initiation_share)}`}</td>
              <td>{fmtDuration(replies[p.name]?.median_s)}</td>
              <td>{fmtDuration(replies[p.name]?.mean_s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResponseTimes({ responseTimes, hasSeconds }) {
  if (!responseTimes.length) return <Empty>Нужно хотя бы два участника.</Empty>;
  const data = {
    labels: responseTimes.map((r) => r.name),
    datasets: [{ data: responseTimes.map((r) => r.median_s / 60), backgroundColor: ACCENT, borderRadius: 4 }],
  };
  const options = {
    ...horizontalOptions,
    scales: {
      ...horizontalOptions.scales,
      x: { beginAtZero: true, title: { display: true, text: "минуты" } },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const r = responseTimes[ctx.dataIndex];
            return [
              ` медиана: ${fmtDuration(r.median_s)}`,
              ` среднее: ${fmtDuration(r.mean_s)}`,
              ` ответов: ${fmtInt(r.responses)}`,
            ];
          },
        },
      },
    },
  };
  return (
    <>
      <div className="chart" style={{ height: Math.max(140, 56 * responseTimes.length) }}>
        <Bar data={data} options={options} />
      </div>
      {!hasSeconds && <p className="note">Время в экспорте без секунд — точность до минуты.</p>}
    </>
  );
}

// --- звонки ------------------------------------------------------------------------------

function Calls({ calls }) {
  if (!calls.total) return <Empty>Звонков в экспорте нет.</Empty>;
  const people = calls.by_participant;
  const data = {
    labels: people.map((p) => p.name),
    datasets: [
      { label: "состоялись", data: people.map((p) => p.completed), backgroundColor: ACCENT, borderRadius: 4 },
      { label: "пропущены", data: people.map((p) => p.missed), backgroundColor: MISSED, borderRadius: 4 },
    ],
  };
  const options = {
    ...horizontalOptions,
    scales: {
      x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
      y: { stacked: true, grid: { display: false } },
    },
    plugins: {
      legend: { display: true, position: "bottom", labels: { boxWidth: 12 } },
      tooltip: {
        callbacks: {
          footer: (items) => `Длительность: ${fmtDuration(people[items[0].dataIndex].duration_s)}`,
        },
      },
    },
  };
  return (
    <>
      <div className="mini-kpis">
        <Kpi value={fmtInt(calls.missed)} label="пропущено" />
        <Kpi value={fmtDuration(calls.total_duration_s)} label="всего на связи" />
        <Kpi value={fmtDuration(calls.avg_duration_s)} label="в среднем" />
        <Kpi value={fmtDuration(calls.longest_s)} label="самый долгий" />
      </div>
      <p className="note">
        Голосовых {fmtInt(calls.voice)}, видео {fmtInt(calls.video)}. По участникам — кто звонил.
      </p>
      <div className="chart" style={{ height: Math.max(150, 50 * people.length + 40) }}>
        <Bar data={data} options={options} />
      </div>
    </>
  );
}

// --- активность ---------------------------------------------------------------------------

function ActivityBars({ labels, values, color }) {
  const data = { labels, datasets: [{ data: values, backgroundColor: color, borderRadius: 3 }] };
  const options = {
    ...baseOptions,
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 6 } },
      y: { beginAtZero: true, ticks: { precision: 0 } },
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => ` ${fmtInt(ctx.raw)} сообщ.` } },
    },
  };
  return (
    <div className="chart">
      <Bar data={data} options={options} />
    </div>
  );
}

// --- эмодзи --------------------------------------------------------------------------------

function EmojiGrid({ emoji }) {
  if (!emoji.length) return <Empty>Эмодзи не найдены.</Empty>;
  const max = emoji[0].count;
  return (
    <div className="emoji-grid">
      {emoji.map((e) => (
        <div className="emoji-card" key={e.emoji} title={`${e.emoji} — ${fmtInt(e.count)}`}>
          <span className="emoji">{e.emoji}</span>
          <span className="emoji-count">{fmtInt(e.count)}</span>
          <span className="emoji-bar">
            <i style={{ width: `${(100 * e.count) / max}%` }} />
          </span>
        </div>
      ))}
    </div>
  );
}

// --- дашборд целиком ------------------------------------------------------------------------

export default function Dashboard({ report, fileName, gapHours, onGapChange, loading, error }) {
  const { meta, summary, participants, response_times: responseTimes, calls, activity, timeline } = report;

  // Цвет участника одинаковый во всех графиках: по порядку в списке (по числу сообщений).
  const colorIndex = Object.fromEntries(meta.participants.map((name, i) => [name, i]));
  const colorOf = (name) => (name in colorIndex ? PALETTE[colorIndex[name] % PALETTE.length] : REST_COLOR);

  return (
    <div className={`dashboard${loading ? " is-loading" : ""}`}>
      <Header meta={meta} fileName={fileName} gapHours={gapHours} onGapChange={onGapChange} loading={loading} />

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {report.warnings.length > 0 && (
        <ul className="warnings">
          {report.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <Kpis summary={summary} calls={calls} />

      {summary.messages === 0 ? (
        <Section title="Пока нечего показывать">
          <Empty>Загрузите другой экспорт — например, чат, где уже есть переписка.</Empty>
        </Section>
      ) : (
        <>
          <div className="grid-2">
            <Section title="Кто пишет больше" subtitle="Доля сообщений">
              <ShareDoughnut data={slices(participants, "messages")} colorOf={colorOf} unit="сообщ." />
            </Section>
            <Section title="Кто начинает разговор" subtitle={`Первое сообщение после паузы больше ${gapHours} ч`}>
              {participants.length > 1 ? (
                <ShareDoughnut data={slices(participants, "initiations")} colorOf={colorOf} unit="раз" />
              ) : (
                <Empty>Нужно хотя бы два участника.</Empty>
              )}
            </Section>
          </div>

          <Section title="Участники">
            <ParticipantsTable participants={participants} responseTimes={responseTimes} />
          </Section>

          <div className="grid-2">
            <Section
              title="Время ответа"
              subtitle={`Медиана паузы перед ответом собеседнику; ответы позже ${gapHours} ч не считаются`}
            >
              <ResponseTimes responseTimes={responseTimes} hasSeconds={meta.has_seconds} />
            </Section>
            <Section title="Звонки">
              <Calls calls={calls} />
            </Section>
          </div>

          <Section title="Когда вы переписываетесь" subtitle="Сообщения по дням недели и часам">
            <Heatmap matrix={activity.matrix} />
          </Section>

          <div className="grid-2">
            <Section title="По часам суток">
              <ActivityBars
                labels={activity.by_hour.map((_, h) => String(h).padStart(2, "0"))}
                values={activity.by_hour}
                color={ACCENT}
              />
            </Section>
            <Section title="По дням недели">
              <ActivityBars labels={WEEKDAYS} values={activity.by_weekday} color={ACCENT_2} />
            </Section>
          </div>

          <Timeline timeline={timeline} />

          <div className="grid-2">
            <Section title="Топ-слова" subtitle="Без стоп-слов и имён участников; наведите на слово, чтобы увидеть число">
              <WordCloud words={report.top_words} />
            </Section>
            <Section title="Топ-эмодзи">
              <EmojiGrid emoji={report.top_emoji} />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}
