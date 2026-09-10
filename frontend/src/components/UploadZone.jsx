import { useEffect, useRef, useState } from "react";

// Синтетический чат из examples/ — Vite кладёт его в сборку отдельным файлом.
import demoChatUrl from "../../../examples/demo_chat.txt?url";

const EXTENSIONS = [".txt", ".zip"];

export default function UploadZone({ onFile, loading, error, maxMb, backendDown }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState("");

  // Проверяем то, что можно проверить без сервера: расширение и размер.
  function pick(file) {
    if (!file || loading) return;
    if (!EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))) {
      setLocalError("Нужен экспорт WhatsApp: файл .txt или .zip.");
      return;
    }
    if (file.size > maxMb * 1024 * 1024) {
      setLocalError(`Файл больше ${maxMb} МБ. Экспортируйте чат без медиа — это один .txt.`);
      return;
    }
    setLocalError("");
    onFile(file);
  }

  // Демо проходит тот же путь, что и настоящий файл: File → POST /api/analyze.
  async function pickDemo() {
    try {
      const blob = await (await fetch(demoChatUrl)).blob();
      pick(new File([blob], "demo_chat.txt", { type: "text/plain" }));
    } catch {
      setLocalError("Не удалось загрузить демо-чат.");
    }
  }

  // Ссылка вида /?demo сразу открывает демо. Параметр убираем из адреса,
  // иначе «Загрузить другой чат» снова открывал бы демо.
  const demoStarted = useRef(false);
  useEffect(() => {
    if (demoStarted.current || !new URLSearchParams(window.location.search).has("demo")) return;
    demoStarted.current = true; // StrictMode в dev вызывает эффект дважды
    window.history.replaceState(null, "", window.location.pathname);
    pickDemo();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };
  // dragleave срабатывает и при переходе на дочерний элемент — такие события пропускаем
  const onDragLeave = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false);
  };
  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files[0]);
  };

  const message = localError || error;

  return (
    <section className="upload">
      <h1>Что происходит в вашем чате?</h1>
      <p className="lead">
        Загрузите экспорт WhatsApp — ChatPulse посчитает, кто пишет больше, кто первым начинает разговор, как быстро
        вы отвечаете и в какие часы чат оживает.
      </p>

      <div
        className={`dropzone${dragging ? " dragging" : ""}${loading ? " busy" : ""}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {loading ? (
          <>
            <div className="spinner" aria-hidden="true" />
            <p>Считаем статистику…</p>
          </>
        ) : (
          <>
            <div className="dropzone-icon" aria-hidden="true">📂</div>
            <p>
              <strong>Перетащите файл сюда</strong> или
            </p>
            <button type="button" className="primary" onClick={() => input.current.click()}>
              Выбрать файл
            </button>
            <p className="hint">.txt или .zip (экспорт с медиа) · до {maxMb} МБ</p>
          </>
        )}
        <input
          ref={input}
          type="file"
          accept=".txt,.zip"
          hidden
          onChange={(e) => {
            pick(e.target.files[0]);
            e.target.value = ""; // чтобы можно было выбрать тот же файл ещё раз
          }}
        />
      </div>

      <p className="demo">
        Нет под рукой экспорта?{" "}
        <button type="button" className="link" onClick={pickDemo} disabled={loading}>
          Попробуйте на демо-чате
        </button>{" "}
        — переписка выдуманная.
      </p>

      {message && (
        <p className="error" role="alert">
          {message}
        </p>
      )}
      {backendDown && !message && (
        <p className="error" role="alert">
          Бэкенд не отвечает. Запустите его — команды есть в README.
        </p>
      )}

      <details className="howto">
        <summary>Как экспортировать чат из WhatsApp</summary>
        <ul>
          <li>
            <strong>Android:</strong> откройте чат → ⋮ → Ещё → Экспорт чата → Без медиафайлов.
          </li>
          <li>
            <strong>iPhone:</strong> откройте чат → нажмите на имя контакта или группы → Экспорт чата → Без
            медиафайлов.
          </li>
          <li>Сохраните файл на компьютер и перетащите сюда — .zip распаковывать не нужно.</li>
        </ul>
      </details>
    </section>
  );
}
