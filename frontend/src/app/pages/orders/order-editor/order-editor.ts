import { Component, inject, input, output } from '@angular/core';
import {
  FormArray,
  FormControl,
  FormGroup,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';

import { Order, OrderItem, OrderOptionsResponse } from '../../../core/orders/orders.models';

export type OrderItemEditorForm = FormGroup<{
  variantId: FormControl<number | null>;
  quantity: FormControl<number | null>;
  unitPrice: FormControl<number | null>;
}>;

export type OrderEditorForm = FormGroup<{
  branchId: FormControl<number | null>;
  warehouseId: FormControl<number | null>;
  customerId: FormControl<number | null>;
  notes: FormControl<string>;
  items: FormArray<OrderItemEditorForm>;
}>;

@Component({
  selector: 'app-order-editor',
  imports: [ReactiveFormsModule],
  templateUrl: './order-editor.html',
  styleUrl: './order-editor.scss',
})
export class OrderEditor {
  private readonly formBuilder = inject(NonNullableFormBuilder);

  readonly editingOrder = input<Order | null>(null);
  readonly options = input.required<OrderOptionsResponse>();
  readonly orderForm = input.required<OrderEditorForm>();
  readonly isSaving = input(false);
  readonly saveErrorMessage = input('');

  readonly closed = output<void>();
  readonly submitted = output<void>();

  addItem(item?: OrderItem): void {
    this.orderForm().controls.items.push(
      this.formBuilder.group({
        variantId: this.formBuilder.control<number | null>(item?.variant ?? null, [
          Validators.required,
        ]),
        quantity: this.formBuilder.control<number | null>(item ? Number(item.quantity) : 1, [
          Validators.required,
          Validators.min(0.001),
        ]),
        unitPrice: this.formBuilder.control<number | null>(item ? Number(item.unit_price) : null, [
          Validators.required,
          Validators.min(0),
        ]),
      }),
    );
  }

  removeItem(index: number): void {
    if (this.orderForm().controls.items.length > 1) {
      this.orderForm().controls.items.removeAt(index);
    }
  }

  onBranchChanged(): void {
    const warehouseId = this.orderForm().controls.warehouseId.value;

    if (
      warehouseId &&
      !this.availableWarehouses().some((warehouse) => warehouse.id === warehouseId)
    ) {
      this.orderForm().controls.warehouseId.setValue(null);
    }
  }

  onVariantChanged(index: number): void {
    const itemForm = this.orderForm().controls.items.at(index);
    const variant = this.options().variants.find(
      (candidate) => candidate.id === itemForm.controls.variantId.value,
    );

    if (variant) {
      itemForm.controls.unitPrice.setValue(Number(variant.base_price));
    }
  }

  availableWarehouses() {
    const branchId = this.orderForm().controls.branchId.value;

    if (!branchId) {
      return this.options().warehouses;
    }

    return this.options().warehouses.filter(
      (warehouse) => warehouse.branch === null || warehouse.branch === branchId,
    );
  }

  closeFromBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.requestClose();
    }
  }

  requestClose(): void {
    if (!this.isSaving()) {
      this.closed.emit();
    }
  }
}
