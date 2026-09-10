// Мелкие общие блоки дашборда: карточка-секция, пустое состояние, крупная цифра.

export function Section({ title, subtitle, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      <h2>{title}</h2>
      {subtitle && <p className="subtitle">{subtitle}</p>}
      {children}
    </section>
  );
}

export function Empty({ children }) {
  return <p className="empty">{children}</p>;
}

export function Kpi({ value, label }) {
  return (
    <div className="kpi">
      <span className="kpi-value">{value}</span>
      <span className="kpi-label">{label}</span>
    </div>
  );
}
