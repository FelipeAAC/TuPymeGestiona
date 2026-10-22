import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-reset-password',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './reset-password.html',
  styleUrl: './reset-password.scss',
})
export class ResetPassword {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly form = this.formBuilder.group({
    password: ['', [Validators.required, Validators.minLength(8)]],
    passwordConfirmation: ['', [Validators.required]],
  });
  readonly isSubmitting = signal(false);
  readonly error = signal('');
  readonly success = signal(false);

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { password, passwordConfirmation } = this.form.getRawValue();
    if (password !== passwordConfirmation) {
      this.error.set('Las contraseñas no coinciden.');
      return;
    }
    const uid = this.route.snapshot.queryParamMap.get('uid') ?? '';
    const token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!uid || !token) {
      this.error.set('El enlace de recuperación no es válido o está incompleto.');
      return;
    }
    this.error.set('');
    this.isSubmitting.set(true);
    this.authService
      .confirmPasswordReset(uid, token, password)
      .pipe(finalize(() => this.isSubmitting.set(false)))
      .subscribe({
        next: () => {
          this.success.set(true);
          setTimeout(() => void this.router.navigate(['/login']), 1200);
        },
        error: (response: HttpErrorResponse) => {
          const passwordError = response.error?.password;
          this.error.set(
            Array.isArray(passwordError)
              ? passwordError.join(' ')
              : response.error?.detail ?? 'El enlace no es válido o expiró.',
          );
        },
      });
  }
}
