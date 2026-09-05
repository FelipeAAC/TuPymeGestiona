import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';

import {
  PortalProduct,
  PortalStore,
  PortalVariant,
} from '../../core/portal/portal.models';
import { PortalService } from '../../core/portal/portal.service';

interface CartLine {
  productId: number;
  productName: string;
  variant: PortalVariant;
  quantity: number;
}

@Component({
  selector: 'app-portal',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './portal.html',
  styleUrl: './portal.scss',
})
export class Portal implements OnInit {
  private readonly portalService = inject(PortalService);
  private readonly authService = inject(AuthService);
  private readonly organizationContextService = inject(OrganizationContextService);
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly router = inject(Router);

  readonly currentUser = this.authService.currentUser;
  readonly memberships = this.organizationContextService.memberships;
  readonly hasActiveMembership = computed(() =>
    this.memberships().some((membership) => membership.status === 'ACTIVE'),
  );
  readonly displayName = computed(() => {
    const user = this.currentUser();
    if (!user) return '';
    return user.first_name.trim() || user.username || user.email;
  });

  readonly stores = signal<PortalStore[]>([]);
  readonly selectedStore = signal<PortalStore | null>(null);
  readonly categories = signal<{ id: number; name: string }[]>([]);
  readonly products = signal<PortalProduct[]>([]);
  readonly selectedProduct = signal<PortalProduct | null>(null);
  readonly cart = signal<CartLine[]>([]);

  readonly isLoadingStores = signal(false);
  readonly isLoadingCatalog = signal(false);
  readonly isLoadingDetail = signal(false);
  readonly isSubmitting = signal(false);
  readonly isRestoringSession = signal(false);
  readonly isLoggingOut = signal(false);
  readonly sessionMessage = signal('');
  readonly errorMessage = signal('');
  readonly checkoutMessage = signal('');

  readonly catalogForm = this.formBuilder.group({
    search: ['', [Validators.maxLength(150)]],
    categoryId: [0],
  });

  readonly checkoutForm = this.formBuilder.group({
    branchId: [0, [Validators.required, Validators.min(1)]],
    address: ['', [Validators.required, Validators.maxLength(220)]],
    commune: ['', [Validators.required, Validators.maxLength(120)]],
    city: ['', [Validators.required, Validators.maxLength(120)]],
    notes: ['', [Validators.maxLength(2000)]],
  });

  readonly cartTotal = computed(() =>
    this.cart().reduce(
      (total, line) => total + Number(line.variant.base_price) * line.quantity,
      0,
    ),
  );

  ngOnInit(): void {
    this.restoreSession();
    this.loadStores();
  }

  logout(): void {
    if (this.isLoggingOut()) return;
    this.sessionMessage.set('');
    this.isLoggingOut.set(true);
    this.authService
      .logout()
      .pipe(finalize(() => this.isLoggingOut.set(false)))
      .subscribe({
        next: () => this.organizationContextService.clear(),
        error: () => this.sessionMessage.set('No pudimos cerrar sesión. Inténtalo nuevamente.'),
      });
  }

  selectStore(store: PortalStore): void {
    if (this.selectedStore()?.id !== store.id) {
      this.cart.set([]);
      this.persistCart();
    }
    this.selectedStore.set(store);
    this.catalogForm.reset({ search: '', categoryId: 0 });
    this.checkoutForm.patchValue({ branchId: store.branches[0]?.id ?? 0 });
    this.loadCatalog();
  }

  applyFilters(): void {
    this.loadCatalog();
  }

  clearFilters(): void {
    this.catalogForm.reset({ search: '', categoryId: 0 });
    this.loadCatalog();
  }

  openProduct(product: PortalProduct): void {
    const store = this.selectedStore();
    if (!store) return;
    this.isLoadingDetail.set(true);
    this.portalService
      .getProduct(store.id, product.id)
      .pipe(finalize(() => this.isLoadingDetail.set(false)))
      .subscribe({
        next: (detail) => this.selectedProduct.set(detail),
        error: () => this.errorMessage.set('No pudimos cargar el detalle del producto.'),
      });
  }

  closeProduct(): void {
    this.selectedProduct.set(null);
  }

  addToCart(product: PortalProduct, variant: PortalVariant): void {
    if (!variant.available) return;
    const current = [...this.cart()];
    const index = current.findIndex((line) => line.variant.id === variant.id);
    if (index >= 0) {
      const available = Math.floor(Number(variant.available_quantity));
      current[index] = {
        ...current[index],
        quantity: Math.min(current[index].quantity + 1, Math.max(available, 1)),
      };
    } else {
      current.push({ productId: product.id, productName: product.name, variant, quantity: 1 });
    }
    this.cart.set(current);
    this.persistCart();
  }

  changeQuantity(variantId: number, delta: number): void {
    const next = this.cart()
      .map((line) => {
        if (line.variant.id !== variantId) return line;
        const max = Math.max(Math.floor(Number(line.variant.available_quantity)), 1);
        return { ...line, quantity: Math.max(0, Math.min(line.quantity + delta, max)) };
      })
      .filter((line) => line.quantity > 0);
    this.cart.set(next);
    this.persistCart();
  }

  submitOrder(): void {
    const store = this.selectedStore();
    if (!store || this.cart().length === 0 || this.isSubmitting()) return;
    if (this.checkoutForm.invalid) {
      this.checkoutForm.markAllAsTouched();
      return;
    }

    const form = this.checkoutForm.getRawValue();
    this.checkoutMessage.set('');
    this.isSubmitting.set(true);
    this.portalService
      .createOrder(
        {
          company: store.id,
          branch: form.branchId,
          delivery_address: form.address.trim(),
          delivery_commune: form.commune.trim(),
          delivery_city: form.city.trim(),
          notes: form.notes.trim(),
          items: this.cart().map((line) => ({
            variant: line.variant.id,
            quantity: line.quantity.toFixed(3),
          })),
        },
        crypto.randomUUID(),
      )
      .pipe(finalize(() => this.isSubmitting.set(false)))
      .subscribe({
        next: (order) => {
          this.cart.set([]);
          this.persistCart();
          this.checkoutMessage.set(`Pedido #${order.number} registrado correctamente.`);
        },
        error: (error: HttpErrorResponse) => {
          if (error.status === 401 || error.status === 403) {
            void this.router.navigate(['/login'], { queryParams: { returnUrl: '/portal' } });
            return;
          }
          this.checkoutMessage.set(
            error.status === 409
              ? (error.error?.detail ?? 'No hay stock suficiente para completar el pedido.')
              : 'No pudimos registrar el pedido. Inténtalo nuevamente.',
          );
        },
      });
  }

  private restoreSession(): void {
    this.isRestoringSession.set(true);
    this.authService
      .me()
      .pipe(finalize(() => this.isRestoringSession.set(false)))
      .subscribe({
        next: () => {
          this.organizationContextService.load().subscribe({
            error: () => this.organizationContextService.clear(),
          });
        },
        error: (error: HttpErrorResponse) => {
          this.organizationContextService.clear();
          if (error.status !== 401 && error.status !== 403) {
            this.sessionMessage.set('No pudimos comprobar tu sesión en este momento.');
          }
        },
      });
  }

  private loadStores(): void {
    this.isLoadingStores.set(true);
    this.portalService
      .listStores()
      .pipe(finalize(() => this.isLoadingStores.set(false)))
      .subscribe({
        next: (stores) => {
          this.stores.set(stores);
          if (stores.length) this.selectStore(stores[0]);
        },
        error: () => this.errorMessage.set('No pudimos cargar las tiendas disponibles.'),
      });
  }

  private loadCatalog(): void {
    const store = this.selectedStore();
    if (!store) return;
    const filters = this.catalogForm.getRawValue();
    this.isLoadingCatalog.set(true);
    this.errorMessage.set('');
    this.portalService
      .getCatalog(store.id, filters.search, filters.categoryId)
      .pipe(finalize(() => this.isLoadingCatalog.set(false)))
      .subscribe({
        next: (response) => {
          this.categories.set(response.categories);
          this.products.set(response.products);
          this.restoreCart(store.id);
        },
        error: () => {
          this.products.set([]);
          this.errorMessage.set('No pudimos cargar el catálogo de esta tienda.');
        },
      });
  }

  private persistCart(): void {
    const storeId = this.selectedStore()?.id;
    if (!storeId) return;
    localStorage.setItem(`tg-portal-cart-${storeId}`, JSON.stringify(this.cart()));
  }

  private restoreCart(storeId: number): void {
    if (this.cart().length) return;
    const raw = localStorage.getItem(`tg-portal-cart-${storeId}`);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as CartLine[];
      this.cart.set(Array.isArray(parsed) ? parsed : []);
    } catch {
      localStorage.removeItem(`tg-portal-cart-${storeId}`);
    }
  }
}
