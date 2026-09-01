import type { ReactNode } from 'react';
import type { StatusVariant } from '../tokens';
import './components.css';

type BadgeProps = {
  children: ReactNode;
  variant?: StatusVariant;
};

export function Badge({ children, variant = 'info' }: BadgeProps) {
  return <span className={`lattice-badge lattice-badge--${variant}`}>{children}</span>;
}

export function StatusBadge({ status, variant }: { status: string; variant: StatusVariant }) {
  return (
    <span className={`lattice-badge lattice-badge--${variant}`}>
      <span className="lattice-badge__dot" aria-hidden="true" />
      {status.replaceAll('_', ' ')}
    </span>
  );
}
