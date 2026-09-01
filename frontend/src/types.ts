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
  };
  session: {
    mfa_enabled: boolean;
    active_warehouse: string | null;
  };
  authorization: {
    membership_id: string;
    roles: string[];
    permissions: string[];
    warehouses: { warehouse_code: string }[];
  };
  modules: string[];
  counts: {
    plants: number;
    warehouses: number;
    zones: number;
    bins: number;
    active_users: number;
    enabled_modules: number;
  };
};
