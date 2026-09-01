import type { ReactNode } from 'react';
import './layouts.css';

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="lattice-page-header">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="lattice-page-header__actions">{actions}</div> : null}
    </div>
  );
}
