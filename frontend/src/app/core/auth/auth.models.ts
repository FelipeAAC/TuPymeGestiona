export interface AuthUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

export interface LoginCredentials {
  identifier: string;
  password: string;
  rememberMe: boolean;
}

export interface LoginResponse {
  user: AuthUser;
}
