export type CurrentUser = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_platform_admin: boolean;
};

export type LoginContext =
  | {
      mode: 'owner';
      title: string;
    }
  | {
      mode: 'tenant';
      tenant: {
        tenant_code: string;
        display_name: string;
        status: string;
      };
    };

export type TenantContext = {
  tenant: {
    id: string;
    tenant_code: string;
    display_name: string;
    status: string;
    license_number: string;
    timezone?: string;
    default_language?: string;
  };
  session: {
    mfa_enabled: boolean;
    active_warehouse: string | null;
  };
  authorization: {
    membership_id: string;
    roles: string[];
    permissions: string[];
    warehouses: Array<{ warehouse_code: string } | string>;
  };
  modules: string[];
  counts: {
    plants: number;
    warehouses: number;
    storage_types: number;
    zones: number;
    sections: number;
    bins: number;
    bays: number;
    active_bays: number;
    blocked_bays: number;
    machines: number;
    people_resources: number;
    configuration_alerts: number;
    active_users: number;
    enabled_modules: number;
  };
};
