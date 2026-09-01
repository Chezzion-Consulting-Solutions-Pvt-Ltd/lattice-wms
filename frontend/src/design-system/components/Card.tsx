import type { ReactNode } from 'react';
import './components.css';

type SurfaceVariant = 'solid' | 'glass';

export function Card({
  title,
  description,
  actions,
  children,
  variant = 'solid',
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  variant?: SurfaceVariant;
}) {
  return (
    <section className={`lattice-card lattice-card--${variant}`}>
      <div className="lattice-card__header">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="lattice-card__actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  icon,
  variant = 'solid',
  tone = 'neutral',
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  variant?: SurfaceVariant;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info';
}) {
  return (
    <div className={`lattice-stat-card lattice-stat-card--${variant} lattice-stat-card--${tone} bg-lattice-surface text-lattice-text-primary border-lattice-border`}>
      {icon ? <span className="lattice-stat-card__icon">{icon}</span> : null}
      <span className="lattice-stat-card__label">{label}</span>
      <strong className="lattice-stat-card__value">{value}</strong>
    </div>
  );
}
