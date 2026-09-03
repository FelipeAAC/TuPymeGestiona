import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly showPassword = signal(false);
  readonly isSubmitting = signal(false);

  readonly authError = signal('');
  readonly authSuccess = signal('');

  readonly loginForm = this.formBuilder.group({
    identifier: ['', Validators.required],
    password: ['', Validators.required],
    rememberMe: [false],
  });

  get identifier() {
    return this.loginForm.controls.identifier;
  }

  get password() {
    return this.loginForm.controls.password;
  }

  togglePasswordVisibility(): void {
    this.showPassword.update((value) => !value);
  }

  onSubmit(): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }

    if (this.isSubmitting()) {
      return;
    }

    this.authError.set('');
    this.authSuccess.set('');
    this.isSubmitting.set(true);

    this.authService
      .login(this.loginForm.getRawValue())
      .pipe(
        finalize(() => {
          this.isSubmitting.set(false);
        }),
      )
      .subscribe({
        next: () => {
          const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
          const safeReturnUrl = returnUrl?.startsWith('/') && !returnUrl.startsWith('//') ? returnUrl : '/app/dashboard';
          void this.router.navigateByUrl(safeReturnUrl);
        },

        error: (error: HttpErrorResponse) => {
          if (error.status === 401) {
            this.authError.set('Correo/usuario o contraseña incorrectos.');
            return;
          }

          if (error.status === 403) {
            this.authError.set(
              'No fue posible validar la solicitud. Recarga la página e inténtalo nuevamente.',
            );
            return;
          }

          if (error.status === 0) {
            this.authError.set('No fue posible conectar con el servidor. Inténtalo nuevamente.');
            return;
          }

          this.authError.set('No pudimos iniciar sesión. Inténtalo nuevamente.');
        },
      });
  }
}
