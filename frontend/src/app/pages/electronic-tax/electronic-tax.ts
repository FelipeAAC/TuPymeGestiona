import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, Subscription } from 'rxjs';

import {
  ElectronicTaxDocument,
  ElectronicTaxListQuery,
  ElectronicTaxPagination,
  ElectronicTaxReferenceReason,
  ElectronicTaxState,
  ElectronicTaxTypeCode,
  FolioAuthorizationSummary,
} from '../../core/electronic-tax/electronic-tax.models';
import { ElectronicTaxService } from '../../core/electronic-tax/electronic-tax.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { Sale } from '../../core/sales/sales.models';
import { SalesService } from '../../core/sales/sales.service';

const EMPTY_PAGINATION: ElectronicTaxPagination = {
  count: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
};

@Component({
  selector: 'app-electronic-tax',
  imports: [ReactiveFormsModule],
  templateUrl: './electronic-tax.html',
  styleUrl: './electronic-tax.scss',
})
export class ElectronicTax implements OnDestroy {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly electronicTaxService = inject(ElectronicTaxService);
  private readonly salesService = inject(SalesService);
  private readonly organizationContextService = inject(OrganizationContextService);

  private listSubscription: Subscription | null = null;
  private folioSubscription: Subscription | null = null;
  private salesSubscription: Subscription | null = null;
  private detailSubscription: Subscription | null = null;
  private mutationSubscription: Subscription | null = null;
  private createIdempotencyKey = '';
  private actionIdempotencyKey = '';
  private noteIdempotencyKey = '';

  readonly selectedMembership = this.organizationContextService.selectedMembership;
  readonly typeCodes: ElectronicTaxTypeCode[] = [33, 34, 56, 61];
  readonly documents = signal<ElectronicTaxDocument[]>([]);
  readonly folioSummary = signal<FolioAuthorizationSummary[]>([]);
  readonly eligibleSales = signal<Sale[]>([]);
  readonly pagination = signal<ElectronicTaxPagination>({ ...EMPTY_PAGINATION });
  readonly activeFilters = signal<ElectronicTaxListQuery>({ page_size: 20 });

  readonly isLoading = signal(false);
  readonly isFolioLoading = signal(false);
  readonly isSalesLoading = signal(false);
  readonly isDetailLoading = signal(false);
  readonly isMutating = signal(false);
  readonly isCreateOpen = signal(false);
  readonly isDetailOpen = signal(false);
  readonly isNoteOpen = signal(false);
  readonly detailDocument = signal<ElectronicTaxDocument | null>(null);
  readonly noteSource = signal<ElectronicTaxDocument | null>(null);
  readonly noteKind = signal<'credit' | 'debit'>('credit');
  readonly discardCandidate = signal<ElectronicTaxDocument | null>(null);

  readonly listErrorMessage = signal('');
  readonly folioErrorMessage = signal('');
  readonly createErrorMessage = signal('');
  readonly detailErrorMessage = signal('');
  readonly actionErrorMessage = signal('');
  readonly noteErrorMessage = signal('');
  readonly successMessage = signal('');

  readonly draftCount = computed(
    () => this.documents().filter((item) => item.state === 'DRAFT').length,
  );
  readonly readyCount = computed(
    () => this.documents().filter((item) => item.state === 'READY').length,
  );
  readonly acceptedCount = computed(
    () =>
      this.documents().filter(
        (item) => item.state === 'ACCEPTED' || item.state === 'ACCEPTED_WITH_REPAIR',
      ).length,
  );
  readonly rejectedCount = computed(
    () => this.documents().filter((item) => item.state === 'REJECTED').length,
  );

  readonly filterForm = this.formBuilder.group({
    branchId: 0,
    typeCode: this.formBuilder.control<ElectronicTaxTypeCode | ''>(''),
    state: this.formBuilder.control<ElectronicTaxState | ''>(''),
    folio: this.formBuilder.control<number | null>(null, [Validators.min(1)]),
    receiverRut: ['', [Validators.maxLength(20)]],
    issueDateFrom: [''],
    issueDateTo: [''],
  });

  readonly createForm = this.formBuilder.group({
    saleId: this.formBuilder.control<number | null>(null, [Validators.required]),
    typeCode: this.formBuilder.control<33 | 34>(33, [Validators.required]),
  });

  readonly noteForm = this.formBuilder.group({
    reason: this.formBuilder.control<ElectronicTaxReferenceReason>('CANCEL_DOCUMENT', [
      Validators.required,
    ]),
    description: ['', [Validators.required, Validators.maxLength(250)]],
    correctionField: [''],
    correctionValue: [''],
  });

  constructor() {
    effect((onCleanup) => {
      const membership = this.selectedMembership();
      this.cancelRequests();
      this.resetWorkspace();

      if (membership) {
        this.loadDocuments(membership.company.id, 1);
        this.loadFolioSummary(membership.company.id);
      }

      onCleanup(() => this.cancelRequests());
    });
  }

  ngOnDestroy(): void {
    this.cancelRequests();
  }

  applyFilters(): void {
    if (this.filterForm.invalid) {
      this.filterForm.markAllAsTouched();
      return;
    }

    const membership = this.selectedMembership();
    if (!membership) return;

    const value = this.filterForm.getRawValue();
    if (value.issueDateFrom && value.issueDateTo && value.issueDateFrom > value.issueDateTo) {
      this.listErrorMessage.set('La fecha desde no puede ser posterior a la fecha hasta.');
      return;
    }

    this.activeFilters.set({
      branch: value.branchId || null,
      type_code: value.typeCode,
      state: value.state,
      folio: value.folio,
      receiver_rut: value.receiverRut.trim(),
      issue_date_from: value.issueDateFrom || undefined,
      issue_date_to: value.issueDateTo || undefined,
      page_size: 20,
    });
    this.loadDocuments(membership.company.id, 1);
  }

  clearFilters(): void {
    const membership = this.selectedMembership();
    this.filterForm.reset({
      branchId: 0,
      typeCode: '',
      state: '',
      folio: null,
      receiverRut: '',
      issueDateFrom: '',
      issueDateTo: '',
    });
    this.activeFilters.set({ page_size: 20 });
    if (membership) this.loadDocuments(membership.company.id, 1);
  }

  goToPage(page: number): void {
    const membership = this.selectedMembership();
    if (
      !membership ||
      page < 1 ||
      page > Math.max(1, this.pagination().total_pages) ||
      this.isLoading()
    )
      return;
    this.loadDocuments(membership.company.id, page);
  }

  openCreate(): void {
    const membership = this.selectedMembership();
    if (!membership || this.isMutating()) return;

    this.createForm.reset({ saleId: null, typeCode: 33 });
    this.createErrorMessage.set('');
    this.createIdempotencyKey = this.newIdempotencyKey('dte-create', membership.company.id);
    this.isCreateOpen.set(true);
    this.loadEligibleSales(membership.company.id);
  }

  closeCreate(): void {
    if (this.isMutating()) return;
    this.isCreateOpen.set(false);
    this.createErrorMessage.set('');
    this.createIdempotencyKey = '';
  }

  createDocument(): void {
    const membership = this.selectedMembership();
    const saleId = this.createForm.controls.saleId.value;
    if (!membership || this.isMutating()) return;
    if (this.createForm.invalid || saleId === null) {
      this.createForm.markAllAsTouched();
      this.createErrorMessage.set('Selecciona una venta y el tipo de factura.');
      return;
    }

    const companyId = membership.company.id;
    this.createIdempotencyKey ||= this.newIdempotencyKey('dte-create', companyId);
    this.mutationSubscription?.unsubscribe();
    this.createErrorMessage.set('');
    this.successMessage.set('');
    this.isMutating.set(true);

    this.mutationSubscription = this.electronicTaxService
      .createDocument(
        companyId,
        saleId,
        this.createForm.controls.typeCode.value,
        this.createIdempotencyKey,
      )
      .pipe(finalize(() => this.finishMutation(companyId)))
      .subscribe({
        next: (response) => {
          if (!this.isCurrentCompany(companyId)) return;
          this.isCreateOpen.set(false);
          this.createIdempotencyKey = '';
          this.successMessage.set(
            response.idempotent_replay
              ? `DTE #${response.document.id} recuperado sin duplicarlo.`
              : `Borrador ${this.typeLabel(response.document.type_code)} creado desde la venta #${response.document.sale}.`,
          );
          this.loadDocuments(companyId, 1);
        },
        error: (error: HttpErrorResponse) => {
          if (this.isCurrentCompany(companyId))
            this.createErrorMessage.set(this.messageForError(error, 'crear el DTE'));
        },
      });
  }

  openDetail(document: ElectronicTaxDocument): void {
    const membership = this.selectedMembership();
    if (!membership) return;

    const companyId = membership.company.id;
    this.detailDocument.set(document);
    this.detailErrorMessage.set('');
    this.isDetailOpen.set(true);
    this.isDetailLoading.set(true);
    this.detailSubscription?.unsubscribe();
    this.detailSubscription = this.electronicTaxService
      .retrieveDocument(companyId, document.id)
      .pipe(finalize(() => this.isCurrentCompany(companyId) && this.isDetailLoading.set(false)))
      .subscribe({
        next: (response) => {
          if (this.isCurrentCompany(companyId)) this.detailDocument.set(response.document);
        },
        error: (error: HttpErrorResponse) => {
          if (this.isCurrentCompany(companyId))
            this.detailErrorMessage.set(this.messageForError(error, 'cargar el detalle'));
        },
      });
  }

  closeDetail(): void {
    if (this.isMutating()) return;
    this.isDetailOpen.set(false);
    this.detailDocument.set(null);
    this.detailErrorMessage.set('');
  }

  canValidate(document: ElectronicTaxDocument): boolean {
    return document.state === 'DRAFT';
  }

  canDiscard(document: ElectronicTaxDocument): boolean {
    return document.state === 'DRAFT' || document.state === 'READY';
  }

  canCreditNote(document: ElectronicTaxDocument): boolean {
    return (
      (document.type_code === 33 || document.type_code === 34 || document.type_code === 56) &&
      this.isAccepted(document)
    );
  }

  canDebitNote(document: ElectronicTaxDocument): boolean {
    return document.type_code === 61 && this.isAccepted(document);
  }

  canDownloadRide(document: ElectronicTaxDocument): boolean {
    return (
      document.folio !== null &&
      [
        'SIGNED',
        'SUBMITTED',
        'PROCESSING',
        'ACCEPTED',
        'ACCEPTED_WITH_REPAIR',
        'REJECTED',
        'CANCELLED_BY_REFERENCE',
      ].includes(document.state)
    );
  }

  validateDocument(document: ElectronicTaxDocument): void {
    if (!this.canValidate(document)) return;
    this.runDocumentMutation(document, 'validate', 'DTE validado y congelado en READY.');
  }

  requestDiscard(document: ElectronicTaxDocument): void {
    if (this.canDiscard(document)) this.discardCandidate.set(document);
  }

  closeDiscard(): void {
    if (!this.isMutating()) this.discardCandidate.set(null);
  }

  confirmDiscard(): void {
    const document = this.discardCandidate();
    if (!document || !this.canDiscard(document)) return;
    this.runDocumentMutation(document, 'discard', 'DTE descartado de forma trazable.', () =>
      this.discardCandidate.set(null),
    );
  }

  openCreditNote(document: ElectronicTaxDocument): void {
    if (!this.canCreditNote(document)) return;
    const defaultReason: ElectronicTaxReferenceReason =
      document.type_code === 56 ? 'CANCEL_DEBIT_NOTE' : 'CANCEL_DOCUMENT';
    this.openNote(document, 'credit', defaultReason);
  }

  openDebitNote(document: ElectronicTaxDocument): void {
    if (!this.canDebitNote(document)) return;
    this.openNote(document, 'debit', 'CANCEL_CREDIT_NOTE');
  }

  closeNote(): void {
    if (this.isMutating()) return;
    this.isNoteOpen.set(false);
    this.noteSource.set(null);
    this.noteErrorMessage.set('');
    this.noteIdempotencyKey = '';
  }

  submitNote(): void {
    const membership = this.selectedMembership();
    const source = this.noteSource();
    if (!membership || !source || this.isMutating()) return;
    if (this.noteForm.invalid) {
      this.noteForm.markAllAsTouched();
      this.noteErrorMessage.set('Completa el motivo y la descripción de la nota.');
      return;
    }

    const value = this.noteForm.getRawValue();
    const correction: Record<string, string> = {};
    if (
      value.reason === 'CORRECT_TEXT' &&
      value.correctionField.trim() &&
      value.correctionValue.trim()
    ) {
      correction[value.correctionField.trim()] = value.correctionValue.trim();
    }
    if (value.reason === 'CORRECT_TEXT' && Object.keys(correction).length === 0) {
      this.noteErrorMessage.set('Para corregir texto indica el campo y el nuevo valor.');
      return;
    }

    const companyId = membership.company.id;
    this.noteIdempotencyKey ||= this.newIdempotencyKey(
      this.noteKind() === 'credit' ? 'dte-nc' : 'dte-nd',
      companyId,
    );
    const request = {
      version: source.version,
      reason: value.reason,
      description: value.description.trim(),
      ...(Object.keys(correction).length > 0 ? { correction } : {}),
    };

    this.mutationSubscription?.unsubscribe();
    this.noteErrorMessage.set('');
    this.successMessage.set('');
    this.isMutating.set(true);
    const operation =
      this.noteKind() === 'credit'
        ? this.electronicTaxService.createCreditNote(
            companyId,
            source.id,
            request,
            this.noteIdempotencyKey,
          )
        : this.electronicTaxService.createDebitNote(
            companyId,
            source.id,
            request,
            this.noteIdempotencyKey,
          );

    this.mutationSubscription = operation
      .pipe(finalize(() => this.finishMutation(companyId)))
      .subscribe({
        next: (response) => {
          if (!this.isCurrentCompany(companyId)) return;
          this.successMessage.set(
            `${this.typeLabel(response.document.type_code)} #${response.document.id} ${response.idempotent_replay ? 'recuperada sin duplicarla' : 'creada correctamente'}.`,
          );
          this.isNoteOpen.set(false);
          this.noteSource.set(null);
          this.noteIdempotencyKey = '';
          this.loadDocuments(companyId, 1);
          if (this.isDetailOpen()) this.openDetail(source);
        },
        error: (error: HttpErrorResponse) => {
          if (this.isCurrentCompany(companyId))
            this.noteErrorMessage.set(this.messageForError(error, 'crear la nota tributaria'));
        },
      });
  }

  downloadRide(document: ElectronicTaxDocument): void {
    const membership = this.selectedMembership();
    if (!membership || !this.canDownloadRide(document)) return;
    const companyId = membership.company.id;
    this.actionErrorMessage.set('');
    this.electronicTaxService.downloadRide(companyId, document.id).subscribe({
      next: (blob) => {
        if (!this.isCurrentCompany(companyId)) return;
        const url = URL.createObjectURL(blob);
        const link = window.document.createElement('a');
        link.href = url;
        link.download = `RIDE_${document.type_code}_${document.folio}.pdf`;
        link.click();
        URL.revokeObjectURL(url);
      },
      error: (error: HttpErrorResponse) => {
        if (this.isCurrentCompany(companyId))
          this.actionErrorMessage.set(this.messageForError(error, 'descargar el RIDE'));
      },
    });
  }

  typeLabel(typeCode: ElectronicTaxTypeCode): string {
    const labels: Record<ElectronicTaxTypeCode, string> = {
      33: 'Factura electrónica',
      34: 'Factura exenta',
      56: 'Nota de débito',
      61: 'Nota de crédito',
    };
    return labels[typeCode];
  }

  stateLabel(state: ElectronicTaxState): string {
    const labels: Record<ElectronicTaxState, string> = {
      DRAFT: 'Borrador',
      READY: 'Lista',
      FOLIO_RESERVED: 'Folio reservado',
      SIGNED: 'Firmada',
      SUBMITTED: 'Enviada',
      PROCESSING: 'Procesando',
      ACCEPTED: 'Aceptada',
      ACCEPTED_WITH_REPAIR: 'Aceptada con reparo',
      REJECTED: 'Rechazada',
      SEND_UNCERTAIN: 'Envío incierto',
      VOIDED_PRE_SUBMISSION: 'Folio anulado',
      CANCELLED_BY_REFERENCE: 'Anulada por referencia',
      DISCARDED: 'Descartada',
    };
    return labels[state];
  }

  reasonLabel(reason: ElectronicTaxReferenceReason): string {
    const labels: Record<ElectronicTaxReferenceReason, string> = {
      CANCEL_DOCUMENT: 'Anular documento',
      CORRECT_TEXT: 'Corregir texto',
      CANCEL_DEBIT_NOTE: 'Anular nota de débito',
      CANCEL_CREDIT_NOTE: 'Anular nota de crédito',
      CORRECT_AMOUNTS: 'Corregir montos',
    };
    return labels[reason];
  }

  eventLabel(eventType: string): string {
    const labels: Record<string, string> = {
      DRAFT_CREATED: 'Borrador creado',
      VALIDATED: 'Documento validado',
      DISCARDED: 'Documento descartado',
      VERSION_CONFLICT: 'Conflicto de versión',
      FOLIO_RESERVED: 'Folio reservado',
      FOLIO_CONSUMED: 'Folio consumido',
      SIGNED: 'Documento firmado',
      SUBMIT_REQUESTED: 'Envío solicitado',
      SUBMITTED: 'Enviado al SII',
      SEND_UNCERTAIN: 'Resultado de envío incierto',
      STATUS_REFRESHED: 'Estado consultado',
      ACCEPTED: 'Aceptado por SII',
      ACCEPTED_WITH_REPAIR: 'Aceptado con reparo',
      REJECTED: 'Rechazado por SII',
      CANCELLED_BY_REFERENCE: 'Anulado por referencia',
      RIDE_GENERATED: 'RIDE generado',
      RECEIVER_DELIVERED: 'Entregado al receptor',
      RECEIVER_RESPONSE_RECORDED: 'Respuesta del receptor registrada',
    };
    return labels[eventType] ?? eventType.replaceAll('_', ' ');
  }

  formatMoney(value: string | number): string {
    return new Intl.NumberFormat('es-CL', {
      style: 'currency',
      currency: 'CLP',
      maximumFractionDigits: 0,
    }).format(Number(value || 0));
  }

  formatDate(value: string | null): string {
    if (!value) return '—';
    return new Intl.DateTimeFormat('es-CL', { dateStyle: 'medium', timeStyle: 'short' }).format(
      new Date(value),
    );
  }

  branchLabel(branchId: number): string {
    const branch = this.selectedMembership()?.branches.find((item) => item.id === branchId);
    return branch ? `${branch.code} · ${branch.name}` : `Sucursal #${branchId}`;
  }

  folioAvailable(typeCode: ElectronicTaxTypeCode): number | null {
    const rows = this.folioSummary().filter(
      (item) => item.type_code === typeCode && item.status === 'ACTIVE',
    );
    if (rows.length === 0) return null;
    return rows.reduce((total, row) => total + row.available, 0);
  }

  nextPage(): number | null {
    return this.pagination().page < this.pagination().total_pages
      ? this.pagination().page + 1
      : null;
  }

  previousPage(): number | null {
    return this.pagination().page > 1 ? this.pagination().page - 1 : null;
  }

  noteReasons(): ElectronicTaxReferenceReason[] {
    const source = this.noteSource();
    if (!source) return [];
    if (this.noteKind() === 'debit') return ['CANCEL_CREDIT_NOTE'];
    if (source.type_code === 56) return ['CANCEL_DEBIT_NOTE'];
    return ['CANCEL_DOCUMENT', 'CORRECT_TEXT'];
  }

  private openNote(
    document: ElectronicTaxDocument,
    kind: 'credit' | 'debit',
    reason: ElectronicTaxReferenceReason,
  ): void {
    const membership = this.selectedMembership();
    if (!membership) return;
    this.noteKind.set(kind);
    this.noteSource.set(document);
    this.noteForm.reset({ reason, description: '', correctionField: '', correctionValue: '' });
    this.noteErrorMessage.set('');
    this.noteIdempotencyKey = this.newIdempotencyKey(
      kind === 'credit' ? 'dte-nc' : 'dte-nd',
      membership.company.id,
    );
    this.isNoteOpen.set(true);
  }

  private runDocumentMutation(
    document: ElectronicTaxDocument,
    action: 'validate' | 'discard',
    success: string,
    afterSuccess?: () => void,
  ): void {
    const membership = this.selectedMembership();
    if (!membership || this.isMutating()) return;
    const companyId = membership.company.id;
    this.actionIdempotencyKey ||= this.newIdempotencyKey(`dte-${action}`, companyId);
    const operation =
      action === 'validate'
        ? this.electronicTaxService.validateDocument(
            companyId,
            document.id,
            document.version,
            this.actionIdempotencyKey,
          )
        : this.electronicTaxService.discardDocument(
            companyId,
            document.id,
            document.version,
            this.actionIdempotencyKey,
          );

    this.mutationSubscription?.unsubscribe();
    this.actionErrorMessage.set('');
    this.successMessage.set('');
    this.isMutating.set(true);
    this.mutationSubscription = operation
      .pipe(finalize(() => this.finishMutation(companyId)))
      .subscribe({
        next: (response) => {
          if (!this.isCurrentCompany(companyId)) return;
          this.actionIdempotencyKey = '';
          this.successMessage.set(
            response.idempotent_replay ? `${success} Respuesta idempotente recuperada.` : success,
          );
          afterSuccess?.();
          this.updateDocument(response.document);
          this.loadDocuments(companyId, this.pagination().page);
          if (this.detailDocument()?.id === response.document.id)
            this.detailDocument.set(response.document);
        },
        error: (error: HttpErrorResponse) => {
          if (this.isCurrentCompany(companyId))
            this.actionErrorMessage.set(
              this.messageForError(
                error,
                action === 'validate' ? 'validar el DTE' : 'descartar el DTE',
              ),
            );
        },
      });
  }

  private loadDocuments(companyId: number, page: number): void {
    this.listSubscription?.unsubscribe();
    this.listErrorMessage.set('');
    this.isLoading.set(true);
    this.listSubscription = this.electronicTaxService
      .listDocuments(companyId, { ...this.activeFilters(), page, page_size: 20 })
      .pipe(finalize(() => this.isCurrentCompany(companyId) && this.isLoading.set(false)))
      .subscribe({
        next: (response) => {
          if (!this.isCurrentCompany(companyId)) return;
          this.documents.set(response.documents);
          this.pagination.set(response.pagination);
        },
        error: (error: HttpErrorResponse) => {
          if (this.isCurrentCompany(companyId)) {
            this.documents.set([]);
            this.pagination.set({ ...EMPTY_PAGINATION });
            this.listErrorMessage.set(this.messageForError(error, 'listar los DTE'));
          }
        },
      });
  }

  private loadFolioSummary(companyId: number): void {
    this.folioSubscription?.unsubscribe();
    this.folioErrorMessage.set('');
    this.isFolioLoading.set(true);
    this.folioSubscription = this.electronicTaxService
      .getFolioSummary(companyId)
      .pipe(finalize(() => this.isCurrentCompany(companyId) && this.isFolioLoading.set(false)))
      .subscribe({
        next: (response) =>
          this.isCurrentCompany(companyId) && this.folioSummary.set(response.authorizations),
        error: (error: HttpErrorResponse) => {
          if (this.isCurrentCompany(companyId)) {
            this.folioSummary.set([]);
            this.folioErrorMessage.set(
              error.status === 403
                ? 'Sin permiso para consultar disponibilidad de folios.'
                : 'No se pudo cargar el resumen de folios.',
            );
          }
        },
      });
  }

  private loadEligibleSales(companyId: number): void {
    this.salesSubscription?.unsubscribe();
    this.isSalesLoading.set(true);
    this.eligibleSales.set([]);
    this.salesSubscription = this.salesService
      .listSales(companyId, { ordering: '-number', page: 1, page_size: 100 })
      .pipe(finalize(() => this.isCurrentCompany(companyId) && this.isSalesLoading.set(false)))
      .subscribe({
        next: (response) => {
          if (!this.isCurrentCompany(companyId)) return;
          const existingSaleIds = new Set(
            this.documents()
              .filter(
                (item) =>
                  (item.type_code === 33 || item.type_code === 34) && item.state !== 'DISCARDED',
              )
              .map((item) => item.sale),
          );
          this.eligibleSales.set(
            response.sales.filter(
              (sale) => sale.status !== 'CANCELLED' && !existingSaleIds.has(sale.id),
            ),
          );
        },
        error: (error: HttpErrorResponse) => {
          if (this.isCurrentCompany(companyId))
            this.createErrorMessage.set(this.messageForError(error, 'cargar ventas elegibles'));
        },
      });
  }

  private updateDocument(document: ElectronicTaxDocument): void {
    this.documents.update((items) =>
      items.map((item) => (item.id === document.id ? document : item)),
    );
  }

  private resetWorkspace(): void {
    this.documents.set([]);
    this.folioSummary.set([]);
    this.eligibleSales.set([]);
    this.pagination.set({ ...EMPTY_PAGINATION });
    this.activeFilters.set({ page_size: 20 });
    this.filterForm.reset({
      branchId: 0,
      typeCode: '',
      state: '',
      folio: null,
      receiverRut: '',
      issueDateFrom: '',
      issueDateTo: '',
    });
    this.isCreateOpen.set(false);
    this.isDetailOpen.set(false);
    this.isNoteOpen.set(false);
    this.detailDocument.set(null);
    this.noteSource.set(null);
    this.discardCandidate.set(null);
    this.listErrorMessage.set('');
    this.folioErrorMessage.set('');
    this.createErrorMessage.set('');
    this.detailErrorMessage.set('');
    this.actionErrorMessage.set('');
    this.noteErrorMessage.set('');
    this.successMessage.set('');
    this.createIdempotencyKey = '';
    this.actionIdempotencyKey = '';
    this.noteIdempotencyKey = '';
    this.isLoading.set(false);
    this.isFolioLoading.set(false);
    this.isSalesLoading.set(false);
    this.isDetailLoading.set(false);
    this.isMutating.set(false);
  }

  private cancelRequests(): void {
    this.listSubscription?.unsubscribe();
    this.folioSubscription?.unsubscribe();
    this.salesSubscription?.unsubscribe();
    this.detailSubscription?.unsubscribe();
    this.mutationSubscription?.unsubscribe();
  }

  private finishMutation(companyId: number): void {
    if (this.isCurrentCompany(companyId)) this.isMutating.set(false);
  }

  private isAccepted(document: ElectronicTaxDocument): boolean {
    return document.state === 'ACCEPTED' || document.state === 'ACCEPTED_WITH_REPAIR';
  }

  private isCurrentCompany(companyId: number): boolean {
    return this.selectedMembership()?.company.id === companyId;
  }

  private newIdempotencyKey(prefix: string, companyId: number): string {
    const uuid =
      globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    return `${prefix}-${companyId}-${uuid}`;
  }

  private messageForError(error: HttpErrorResponse, action: string): string {
    const detail = typeof error.error?.detail === 'string' ? error.error.detail : '';
    if (detail) return detail;
    if (error.status === 0)
      return `No fue posible ${action}. Revisa la conexión y vuelve a intentar.`;
    if (error.status === 403) return `No tienes permiso para ${action}.`;
    if (error.status === 404) return 'El recurso ya no existe en la empresa activa.';
    if (error.status === 409) return `No fue posible ${action} por el estado actual del documento.`;
    return `No fue posible ${action}.`;
  }
}
