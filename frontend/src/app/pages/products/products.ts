import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';

import { CatalogProduct } from '../../core/catalog/catalog.models';
import { CatalogService } from '../../core/catalog/catalog.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

@Component({
  selector: 'app-products',
  imports: [],
  templateUrl: './products.html',
  styleUrl: './products.scss',
})
export class Products {
  private readonly catalogService = inject(CatalogService);
  private readonly organizationContextService = inject(OrganizationContextService);

  readonly selectedMembership = this.organizationContextService.selectedMembership;

  readonly products = signal<CatalogProduct[]>([]);
  readonly isLoading = signal(false);
  readonly errorMessage = signal('');

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();

      this.products.set([]);
      this.errorMessage.set('');

      if (!membership) {
        this.isLoading.set(false);
        return;
      }

      this.isLoading.set(true);

      const subscription = this.catalogService
        .listProducts(membership.company.id)
        .pipe(finalize(() => this.isLoading.set(false)))
        .subscribe({
          next: (products) => {
            this.products.set(products);
          },
          error: (error: HttpErrorResponse) => {
            this.products.set([]);

            if (error.status === 403) {
              this.errorMessage.set('No tienes permiso para ver los productos de esta empresa.');
              return;
            }

            this.errorMessage.set('No pudimos cargar los productos. Inténtalo nuevamente.');
          },
        });

      onCleanup(() => {
        subscription.unsubscribe();
      });
    });
  }
}
