import { Fragment } from "react";

import { WEEKDAYS, fmtInt } from "../format.js";

const HOURS = Array.from({ length: 24 }, (_, h) => h);
const pad = (h) => String(h).padStart(2, "0");

// В Chart.js нет тепловой карты без плагинов, а CSS-сетка 7×24 делает то же
// самое проще: цвет ячейки — смесь акцента с фоном, пропорционально числу сообщений.
export default function Heatmap({ matrix }) {
  const max = Math.max(1, ...matrix.flat());
  // даже одно сообщение должно быть заметно — у ненулевых ячеек минимальная яркость
  const level = (v) => (v ? 0.1 + (0.9 * v) / max : 0);

  return (
    <>
      <div className="heatmap-scroll">
        <div className="heatmap" role="img" aria-label="Тепловая карта сообщений по дням недели и часам">
          <span />
          {HOURS.map((h) => (
            <span key={h} className="hm-hour">
              {h % 3 === 0 ? pad(h) : ""}
            </span>
          ))}
          {matrix.map((row, day) => (
            <Fragment key={day}>
              <span className="hm-day">{WEEKDAYS[day]}</span>
              {row.map((value, h) => (
                <span
                  key={h}
                  className="hm-cell"
                  style={{ "--level": level(value) }}
                  title={`${WEEKDAYS[day]}, ${pad(h)}:00–${pad(h)}:59 — ${fmtInt(value)} сообщ.`}
                />
              ))}
            </Fragment>
          ))}
        </div>
      </div>
      <div className="hm-legend" aria-hidden="true">
        меньше
        {[0, 0.25, 0.5, 0.75, 1].map((l) => (
          <span key={l} className="hm-cell" style={{ "--level": l }} />
        ))}
        больше
      </div>
    </>
  );
}
