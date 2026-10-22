import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-forgot-password',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.scss',
})
export class ForgotPassword {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly authService = inject(AuthService);

  readonly form = this.formBuilder.group({ email: ['', [Validators.required, Validators.email]] });
  readonly isSubmitting = signal(false);
  readonly sent = signal(false);
  readonly error = signal('');

  submit(): void {
    if (this.form.invalid || this.isSubmitting()) {
      this.form.markAllAsTouched();
      return;
    }
    this.error.set('');
    this.isSubmitting.set(true);
    this.authService
      .requestPasswordReset(this.form.controls.email.value)
      .pipe(finalize(() => this.isSubmitting.set(false)))
      .subscribe({
        next: () => this.sent.set(true),
        error: (response: HttpErrorResponse) => {
          this.error.set(
            response.status === 0
              ? 'No pudimos conectar con el servidor. Inténtalo nuevamente.'
              : 'No pudimos procesar la solicitud. Inténtalo nuevamente.',
          );
        },
      });
  }
}
