import { useCallback, useEffect, useState } from "react";

import { analyzeChat, fetchHealth } from "./api.js";
import { applyChartTheme } from "./charts.js";
import Dashboard from "./components/Dashboard.jsx";
import UploadZone from "./components/UploadZone.jsx";

const DEFAULT_GAP_HOURS = 6;

export default function App() {
  // Файл держим только в памяти вкладки — чтобы пересчитать отчёт с другой паузой.
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [gapHours, setGapHours] = useState(DEFAULT_GAP_HOURS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null); // null — ещё не знаем, false — бэкенд не отвечает
  const [themeVersion, setThemeVersion] = useState(0);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(false));
  }, []);

  // Графики Chart.js не видят CSS-переменные сами: при смене системной темы
  // обновляем их цвета и перерисовываем дашборд.
  useEffect(() => {
    applyChartTheme();
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      applyChartTheme();
      setThemeVersion((v) => v + 1);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const analyze = useCallback(async (nextFile, nextGap) => {
    setLoading(true);
    setError("");
    try {
      const data = await analyzeChat(nextFile, { gapHours: nextGap });
      setFile(nextFile);
      setGapHours(nextGap);
      setReport(data);
      setHealth((h) => h || { status: "ok" });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = () => {
    setFile(null);
    setReport(null);
    setError("");
  };

  return (
    <div className="app">
      <header className="topbar">
        <button type="button" className="brand" onClick={reset}>
          <span aria-hidden="true">💬</span> ChatPulse
        </button>
        {report && (
          <button type="button" className="ghost" onClick={reset}>
            Загрузить другой чат
          </button>
        )}
      </header>

      <main className="wrap">
        {report ? (
          <Dashboard
            key={themeVersion}
            report={report}
            fileName={file.name}
            gapHours={gapHours}
            onGapChange={(gap) => analyze(file, gap)}
            loading={loading}
            error={error}
          />
        ) : (
          <UploadZone
            onFile={(f) => analyze(f, gapHours)}
            loading={loading}
            error={error}
            maxMb={health?.max_upload_mb ?? 200}
            backendDown={health === false}
          />
        )}
      </main>

      <footer className="footer">
        🔒 Файл анализируется в памяти локального бэкенда и нигде не сохраняется. Сторонних запросов страница не делает.
      </footer>
    </div>
  );
}
