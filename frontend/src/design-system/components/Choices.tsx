import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group';
import * as SelectPrimitive from '@radix-ui/react-select';
import { Check, ChevronDown } from 'lucide-react';
import './components.css';

export function Checkbox({ label, checked }: { label: string; checked: boolean }) {
  return (
    <label className="lattice-choice-row">
      <CheckboxPrimitive.Root className="lattice-checkbox" checked={checked} aria-label={label}>
        <CheckboxPrimitive.Indicator>
          <Check size={14} />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      <span>{label}</span>
    </label>
  );
}

export function RadioGroup({
  label,
  value,
  options,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <RadioGroupPrimitive.Root className="lattice-radio-group" value={value} aria-label={label}>
      {options.map((option) => (
        <label className="lattice-choice-row" key={option.value}>
          <RadioGroupPrimitive.Item className="lattice-radio" value={option.value} />
          <span>{option.label}</span>
        </label>
      ))}
    </RadioGroupPrimitive.Root>
  );
}

export function Select({
  label,
  value,
  options,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <SelectPrimitive.Root value={value}>
      <SelectPrimitive.Trigger className="lattice-select" aria-label={label}>
        <SelectPrimitive.Value />
        <SelectPrimitive.Icon>
          <ChevronDown size={15} />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content className="lattice-menu">
          <SelectPrimitive.Viewport>
            {options.map((option) => (
              <SelectPrimitive.Item className="lattice-menu__item" value={option.value} key={option.value}>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
