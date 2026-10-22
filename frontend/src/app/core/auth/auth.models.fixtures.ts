import {
  AuthUser,
  PasswordResetConfirmation,
  PasswordResetResponse,
  PasswordResetState,
} from './auth.models';

export const customerOnlyFixture = {
  access_modes: ['CUSTOMER'],
  default_app: 'portal',
} satisfies Pick<AuthUser, 'access_modes' | 'default_app'>;

export const companyAdminFixture = {
  access_modes: ['COMPANY_ADMIN'],
  default_app: 'app',
} satisfies Pick<AuthUser, 'access_modes' | 'default_app'>;

export const dualAccessFixture = {
  access_modes: ['CUSTOMER', 'COMPANY_ADMIN'],
  default_app: 'choose',
} satisfies Pick<AuthUser, 'access_modes' | 'default_app'>;

export const passwordResetFixture = {
  detail: 'Si la cuenta existe, recibirás instrucciones para continuar.',
} satisfies PasswordResetResponse;

export const passwordResetConfirmationFixture = {
  uid: 'MQ',
  token: 'opaque-token',
  password: 'NewStrongPassword123!',
} satisfies PasswordResetConfirmation;

export const passwordResetStates = [
  'idle',
  'submitting',
  'sent',
  'success',
  'error',
] as const satisfies readonly PasswordResetState[];
