import * as AlertDialog from '@radix-ui/react-alert-dialog';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as DropdownPrimitive from '@radix-ui/react-dropdown-menu';
import * as PopoverPrimitive from '@radix-ui/react-popover';
import * as SwitchPrimitive from '@radix-ui/react-switch';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import type { ReactNode } from 'react';
import { Button } from './Button';
import './components.css';

type DialogProps = {
  title: string;
  description?: string;
  trigger: ReactNode;
  children: ReactNode;
};

export function Dialog({ title, description, trigger, children }: DialogProps) {
  return (
    <DialogPrimitive.Root>
      <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="lattice-dialog__overlay" />
        <DialogPrimitive.Content className="lattice-dialog">
          <DialogPrimitive.Title className="lattice-dialog__title">{title}</DialogPrimitive.Title>
          {description ? <DialogPrimitive.Description className="lattice-dialog__description">{description}</DialogPrimitive.Description> : null}
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function DialogClose({ children }: { children: ReactNode }) {
  return <DialogPrimitive.Close asChild>{children}</DialogPrimitive.Close>;
}

export function ConfirmationDialog({
  title,
  description,
  trigger,
  confirmLabel = 'Confirm',
}: {
  title: string;
  description: string;
  trigger: ReactNode;
  confirmLabel?: string;
}) {
  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger asChild>{trigger}</AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="lattice-dialog__overlay" />
        <AlertDialog.Content className="lattice-dialog">
          <AlertDialog.Title className="lattice-dialog__title">{title}</AlertDialog.Title>
          <AlertDialog.Description className="lattice-dialog__description">{description}</AlertDialog.Description>
          <div className="lattice-dialog__actions">
            <AlertDialog.Cancel asChild>
              <Button variant="secondary">Cancel</Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <Button variant="danger">{confirmLabel}</Button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}

export function DropdownMenu({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  return (
    <DropdownPrimitive.Root>
      <DropdownPrimitive.Trigger asChild>{trigger}</DropdownPrimitive.Trigger>
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content className="lattice-menu" align="end">
          {children}
        </DropdownPrimitive.Content>
      </DropdownPrimitive.Portal>
    </DropdownPrimitive.Root>
  );
}

export function DropdownItem({ children, onSelect }: { children: ReactNode; onSelect?: () => void }) {
  const props = onSelect ? { onSelect } : {};
  return (
    <DropdownPrimitive.Item className="lattice-menu__item" {...props}>
      {children}
    </DropdownPrimitive.Item>
  );
}

export function Popover({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content className="lattice-popover" align="start">
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={250}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content className="lattice-tooltip">{label}</TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

export function Tabs({
  items,
}: {
  items: Array<{
    value: string;
    label: string;
    content: ReactNode;
  }>;
}) {
  const [firstItem] = items;
  if (!firstItem) {
    return null;
  }

  return (
    <TabsPrimitive.Root className="lattice-tabs" defaultValue={firstItem.value}>
      <TabsPrimitive.List className="lattice-tabs__list" aria-label="Section tabs">
        {items.map((item) => (
          <TabsPrimitive.Trigger className="lattice-tabs__trigger" value={item.value} key={item.value}>
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {items.map((item) => (
        <TabsPrimitive.Content className="lattice-tabs__content" value={item.value} key={item.value}>
          {item.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}

export function Switch({ checked, label }: { checked: boolean; label: string }) {
  return (
    <label className="lattice-switch-row">
      <span>{label}</span>
      <SwitchPrimitive.Root className="lattice-switch" checked={checked} aria-label={label}>
        <SwitchPrimitive.Thumb className="lattice-switch__thumb" />
      </SwitchPrimitive.Root>
    </label>
  );
}
