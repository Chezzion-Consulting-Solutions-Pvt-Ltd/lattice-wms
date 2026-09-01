import { useState } from 'react';
import './components.css';

export function BrandLogo({ compact = false }: { compact?: boolean }) {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <span className={compact ? 'lattice-brand-logo lattice-brand-logo--compact' : 'lattice-brand-logo'}>
      {imageFailed ? (
        <span className="lattice-brand-logo__fallback">Lattice</span>
      ) : (
        <img src="/lattice-logo.png" alt="Lattice" onError={() => setImageFailed(true)} />
      )}
    </span>
  );
}
