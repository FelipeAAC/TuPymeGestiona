import { Component, computed, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-access-chooser',
  imports: [RouterLink],
  templateUrl: './access-chooser.html',
  styleUrl: './access-chooser.scss',
})
export class AccessChooser {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly user = this.authService.currentUser;
  readonly canShop = computed(() => this.authService.hasAccessMode('CUSTOMER'));
  readonly canManage = computed(() => this.authService.hasAccessMode('COMPANY_ADMIN'));
  readonly isPlatformAdmin = computed(() => this.authService.hasAccessMode('PLATFORM_ADMIN'));

  choose(path: '/portal' | '/app'): void {
    void this.router.navigateByUrl(path);
  }
}
