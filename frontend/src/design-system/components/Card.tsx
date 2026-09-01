import type { ReactNode } from 'react';
import './components.css';

type SurfaceVariant = 'solid' | 'glass';

export function Card({ title, children, variant = 'solid' }: { title: string; children: ReactNode; variant?: SurfaceVariant }) {
  return (
    <section className={`lattice-card lattice-card--${variant}`}>
      <h2>{title}</h2>
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
