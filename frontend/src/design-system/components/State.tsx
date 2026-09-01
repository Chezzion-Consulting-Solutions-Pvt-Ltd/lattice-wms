import { AlertCircle, Loader2, PackageOpen } from 'lucide-react';
import './components.css';

export function EmptyState({ title }: { title: string }) {
  return (
    <div className="lattice-state">
      <PackageOpen size={24} />
      <p>{title}</p>
    </div>
  );
}

export function LoadingState({ title = 'Loading' }: { title?: string }) {
  return (
    <div className="lattice-state">
      <Loader2 size={24} />
      <p>{title}</p>
    </div>
  );
}

export function ErrorState({ title }: { title: string }) {
  return (
    <div className="lattice-state lattice-state--error">
      <AlertCircle size={24} />
      <p>{title}</p>
    </div>
  );
}
