export interface AuthUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  access_modes: AccessMode[];
  default_app: DefaultApp | null;
  managed_companies: AccessCompany[];
  portal_companies: AccessCompany[];
}

export type AccessMode = 'CUSTOMER' | 'COMPANY_ADMIN' | 'PLATFORM_ADMIN';
export type DefaultApp = 'portal' | 'app' | 'maintainers' | 'choose';

export interface AccessCompany {
  id: number;
  name: string;
}

export interface LoginCredentials {
  identifier: string;
  password: string;
  rememberMe: boolean;
}

export interface LoginResponse {
  user: AuthUser;
}

export interface PasswordResetResponse {
  detail: string;
}

export type PasswordResetState = 'idle' | 'submitting' | 'sent' | 'success' | 'error';

export interface PasswordResetConfirmation {
  uid: string;
  token: string;
  password: string;
}
