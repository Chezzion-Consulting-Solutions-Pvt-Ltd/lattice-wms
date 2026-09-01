import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './components.css';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  icon?: ReactNode;
};

export function Button({ variant = 'primary', icon, children, className = '', ...props }: ButtonProps) {
  return (
    <button className={`lattice-button lattice-button--${variant} ${className}`} {...props}>
      {icon ? <span className="lattice-button__icon">{icon}</span> : null}
      <span>{children}</span>
    </button>
  );
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  icon: ReactNode;
};

export function IconButton({ label, icon, className = '', ...props }: IconButtonProps) {
  return (
    <button className={`lattice-icon-button ${className}`} aria-label={label} title={label} {...props}>
      {icon}
    </button>
  );
}
