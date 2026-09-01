export const statusVariantByBusinessStatus = {
  CREATED: 'info',
  IN_PROGRESS: 'info',
  PENDING: 'warning',
  COMPLETED: 'success',
  CANCELLED: 'danger',
  BLOCKED: 'warning',
  FAILED: 'danger',
  WARNING: 'warning',
} as const;

export type StatusVariant = 'success' | 'warning' | 'danger' | 'info';
