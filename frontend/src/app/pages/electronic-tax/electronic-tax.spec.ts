import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, Subject, throwError } from 'rxjs';

import {
  ElectronicTaxDocument,
  FolioSummaryResponse,
} from '../../core/electronic-tax/electronic-tax.models';
import { ElectronicTaxService } from '../../core/electronic-tax/electronic-tax.service';
import { OrganizationContextService } from '../../core/organization/organization-context.service';
import { OrganizationMembership } from '../../core/organization/organization.models';
import { Sale, SaleListResponse } from '../../core/sales/sales.models';
import { SalesService } from '../../core/sales/sales.service';
import { ElectronicTax } from './electronic-tax';

describe('ElectronicTax', () => {
  let fixture: ComponentFixture<ElectronicTax>;
  let component: ElectronicTax;

  const membership: OrganizationMembership = {
    id: 2,
    status: 'ACTIVE',
    company: { id: 7, name: 'Comercial Andina SpA' },
    branches: [{ id: 3, code: 'SUC-NORTE', name: 'Sucursal Norte' }],
  };
  const secondMembership: OrganizationMembership = {
    id: 4,
    status: 'ACTIVE',
    company: { id: 9, name: 'Servicios del Sur Ltda.' },
    branches: [],
  };

  const sale: Sale = {
    id: 31,
    company: 7,
    branch: 3,
    order: 15,
    order_number: 104,
    customer: 21,
    customer_code: 'CLI-21',
    customer_name: 'Cliente Andino',
    number: 8,
    status: 'PENDING',
    total_amount: '11900.00',
    paid_amount: '0.00',
    balance: '11900.00',
    idempotency_key: 'sale-key',
    created_by: 5,
    cancelled_by: null,
    created_at: '2026-09-03T10:00:00Z',
    updated_at: '2026-09-03T10:00:00Z',
    cancelled_at: null,
    payments: [],
    events: [],
  };

  const draft: ElectronicTaxDocument = {
    id: 9,
    company: 7,
    branch: 3,
    sale: 31,
    type_code: 33,
    state: 'DRAFT',
    version: 1,
    issuer_rut: '76123456-7',
    issuer_legal_name: 'Comercial Andina SpA',
    issuer_business_activity: 'Comercio',
    issuer_address: 'Av. Uno 123',
    issuer_commune: 'Santiago',
    issuer_city: 'Santiago',
    issuer_tax_email: 'tributario@andina.cl',
    receiver_rut: '96543210-8',
    receiver_legal_name: 'Cliente Andino Ltda.',
    receiver_business_activity: 'Servicios',
    receiver_address: 'Calle Dos 456',
    receiver_commune: 'Providencia',
    receiver_city: 'Santiago',
    receiver_tax_email: 'dte@cliente.cl',
    net_amount: '10000',
    exempt_amount: '0',
    vat_rate: '19',
    vat_amount: '1900',
    total_amount: '11900',
    currency: 'CLP',
    issue_date: null,
    folio: null,
    provider_track_id: '',
    provider_status_code: '',
    provider_status_message: '',
    provider_last_checked_at: null,
    snapshot_hash: 'snap',
    xml_hash: '',
    correlation_id: 'corr',
    created_by: 5,
    created_at: '2026-09-03T15:00:00Z',
    updated_at: '2026-09-03T15:00:00Z',
    discarded_at: null,
    lines: [
      {
        id: 1,
        line_number: 1,
        variant: 4,
        sku: 'SKU-1',
        description: 'Servicio tributado',
        quantity: '1.0000',
        unit_price: '10000',
        discount_amount: '0',
        tax_category: 'AFFECTED',
        net_amount: '10000',
        exempt_amount: '0',
        vat_amount: '1900',
        total_amount: '11900',
      },
    ],
    references: [],
    events: [
      {
        id: 1,
        event_type: 'DRAFT_CREATED',
        actor: 5,
        correlation_id: 'corr',
        normalized_code: 'DRAFT_CREATED',
        metadata: {},
        created_at: '2026-09-03T15:00:00Z',
      },
    ],
    exchange: null,
  };
  const ready: ElectronicTaxDocument = { ...draft, state: 'READY', version: 2 };
  const accepted: ElectronicTaxDocument = {
    ...draft,
    state: 'ACCEPTED',
    version: 7,
    folio: 88,
    issue_date: '2026-09-03',
    provider_track_id: 'TRACK-1',
    provider_status_code: 'DOK',
  };

  const listResponse = {
    documents: [draft],
    pagination: { count: 1, page: 1, page_size: 20, total_pages: 1 },
  };
  const emptyListResponse = {
    documents: [],
    pagination: { count: 0, page: 1, page_size: 20, total_pages: 0 },
  };
  const folios: FolioSummaryResponse = {
    authorizations: [
      {
        type_code: 33,
        status: 'ACTIVE',
        start_folio: 1,
        end_folio: 100,
        next_folio: 10,
        available: 91,
      },
    ],
  };
  const salesResponse: SaleListResponse = {
    sales: [sale],
    pagination: {
      count: 1,
      page: 1,
      page_size: 100,
      total_pages: 1,
      next_page: null,
      previous_page: null,
    },
  };

  const selectedMembership = signal<OrganizationMembership | null>(membership);
  const taxService = {
    listDocuments: vi.fn((_companyId: number, _query: unknown) => of(listResponse)),
    getFolioSummary: vi.fn((_companyId: number) => of(folios)),
    retrieveDocument: vi.fn((_companyId: number, _documentId: number) => of({ document: draft })),
    createDocument: vi.fn((_companyId: number, _saleId: number, _type: number, _key: string) =>
      of({ document: draft, idempotent_replay: false }),
    ),
    validateDocument: vi.fn(
      (_companyId: number, _documentId: number, _version: number, _key: string) =>
        of({ document: ready, idempotent_replay: false }),
    ),
    discardDocument: vi.fn(
      (_companyId: number, _documentId: number, _version: number, _key: string) =>
        of({ document: { ...draft, state: 'DISCARDED', version: 2 }, idempotent_replay: false }),
    ),
    createCreditNote: vi.fn(
      (_companyId: number, _documentId: number, _request: unknown, _key: string) =>
        of({ document: { ...draft, id: 12, type_code: 61 }, idempotent_replay: false }),
    ),
    createDebitNote: vi.fn(
      (_companyId: number, _documentId: number, _request: unknown, _key: string) =>
        of({ document: { ...draft, id: 13, type_code: 56 }, idempotent_replay: false }),
    ),
    downloadRide: vi.fn((_companyId: number, _documentId: number) =>
      of(new Blob(['pdf'], { type: 'application/pdf' })),
    ),
  };
  const salesService = {
    listSales: vi.fn((_companyId: number, _query: unknown) => of(salesResponse)),
  };
  const organizationContextService = { selectedMembership: selectedMembership.asReadonly() };

  beforeEach(async () => {
    for (const mock of Object.values(taxService)) mock.mockReset();
    taxService.listDocuments.mockReturnValue(of(listResponse));
    taxService.getFolioSummary.mockReturnValue(of(folios));
    taxService.retrieveDocument.mockReturnValue(of({ document: draft }));
    taxService.createDocument.mockReturnValue(of({ document: draft, idempotent_replay: false }));
    taxService.validateDocument.mockReturnValue(of({ document: ready, idempotent_replay: false }));
    taxService.discardDocument.mockReturnValue(
      of({ document: { ...draft, state: 'DISCARDED', version: 2 }, idempotent_replay: false }),
    );
    taxService.createCreditNote.mockReturnValue(
      of({ document: { ...draft, id: 12, type_code: 61 }, idempotent_replay: false }),
    );
    taxService.createDebitNote.mockReturnValue(
      of({ document: { ...draft, id: 13, type_code: 56 }, idempotent_replay: false }),
    );
    taxService.downloadRide.mockReturnValue(of(new Blob(['pdf'], { type: 'application/pdf' })));
    salesService.listSales.mockReset();
    salesService.listSales.mockReturnValue(of(salesResponse));
    selectedMembership.set(membership);

    await TestBed.configureTestingModule({
      imports: [ElectronicTax],
      providers: [
        { provide: ElectronicTaxService, useValue: taxService },
        { provide: SalesService, useValue: salesService },
        { provide: OrganizationContextService, useValue: organizationContextService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ElectronicTax);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('loads DTE and folio availability for the active company', () => {
    expect(taxService.listDocuments).toHaveBeenCalledWith(7, { page_size: 20, page: 1 });
    expect(taxService.getFolioSummary).toHaveBeenCalledWith(7);
    expect(component.documents()).toEqual([draft]);
    expect(component.folioAvailable(33)).toBe(91);
    expect(fixture.nativeElement.textContent).toContain('Facturación electrónica');
    expect(fixture.nativeElement.textContent).toContain('Cliente Andino Ltda.');
  });

  it('clears tenant data and reloads when the company changes', async () => {
    taxService.listDocuments.mockImplementation((companyId: number) =>
      of(companyId === 7 ? listResponse : emptyListResponse),
    );
    selectedMembership.set(secondMembership);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(taxService.listDocuments).toHaveBeenLastCalledWith(9, { page_size: 20, page: 1 });
    expect(taxService.getFolioSummary).toHaveBeenLastCalledWith(9);
    expect(component.documents()).toEqual([]);
  });

  it('creates a base invoice from an eligible non-cancelled sale with idempotency', () => {
    component.openCreate();
    component.createForm.setValue({ saleId: 31, typeCode: 33 });
    component.createDocument();

    const [companyId, saleId, typeCode, key] = taxService.createDocument.mock.calls[0];
    expect([companyId, saleId, typeCode]).toEqual([7, 31, 33]);
    expect(key).toMatch(/^dte-create-7-/);
    expect(component.successMessage()).toContain('Borrador Factura electrónica creado');
    expect(component.isCreateOpen()).toBe(false);
  });

  it('keeps the same idempotency key after a transient create failure', () => {
    taxService.createDocument
      .mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 0 })))
      .mockReturnValueOnce(of({ document: draft, idempotent_replay: true }));
    component.openCreate();
    component.createForm.setValue({ saleId: 31, typeCode: 33 });

    component.createDocument();
    component.createDocument();

    expect(taxService.createDocument.mock.calls[0][3]).toBe(
      taxService.createDocument.mock.calls[1][3],
    );
    expect(component.successMessage()).toContain('recuperado sin duplicarlo');
  });

  it('validates a DRAFT using its current version and updates the list', () => {
    component.validateDocument(draft);

    const [companyId, documentId, version, key] = taxService.validateDocument.mock.calls[0];
    expect([companyId, documentId, version]).toEqual([7, 9, 1]);
    expect(key).toMatch(/^dte-validate-7-/);
    expect(component.successMessage()).toContain('READY');
  });

  it('requires confirmation before discarding a DRAFT or READY document', () => {
    component.requestDiscard(draft);
    expect(component.discardCandidate()).toEqual(draft);
    expect(taxService.discardDocument).not.toHaveBeenCalled();

    component.confirmDiscard();
    expect(taxService.discardDocument).toHaveBeenCalledWith(
      7,
      9,
      1,
      expect.stringMatching(/^dte-discard-7-/),
    );
    expect(component.discardCandidate()).toBeNull();
  });

  it('loads fiscal detail including lines and chronological evidence', () => {
    taxService.retrieveDocument.mockReturnValueOnce(of({ document: accepted }));
    component.openDetail(accepted);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Totales fiscales');
    expect(text).toContain('Servicio tributado');
    expect(text).toContain('Cronología fiscal');
    expect(text).toContain('Borrador creado');
  });

  it('creates a credit note only from an accepted supported source', () => {
    component.openCreditNote(accepted);
    component.noteForm.setValue({
      reason: 'CANCEL_DOCUMENT',
      description: 'Anulación total por error de emisión',
      correctionField: '',
      correctionValue: '',
    });
    component.submitNote();

    expect(taxService.createCreditNote).toHaveBeenCalledWith(
      7,
      9,
      expect.objectContaining({ version: 7, reason: 'CANCEL_DOCUMENT' }),
      expect.stringMatching(/^dte-nc-7-/),
    );
    expect(component.successMessage()).toContain('Nota de crédito');
  });

  it('does not let a folio-summary permission error block the DTE list', () => {
    taxService.getFolioSummary.mockReturnValueOnce(
      throwError(() => new HttpErrorResponse({ status: 403, error: { detail: 'denied' } })),
    );

    selectedMembership.set(secondMembership);
    fixture.detectChanges();

    expect(component.folioErrorMessage()).toContain('Sin permiso');
  });

  it('cancels stale in-flight list results after a company change', async () => {
    const pending = new Subject<typeof listResponse>();
    taxService.listDocuments.mockReturnValueOnce(pending.asObservable());
    selectedMembership.set(secondMembership);
    fixture.detectChanges();
    await fixture.whenStable();
    selectedMembership.set(membership);
    fixture.detectChanges();
    await fixture.whenStable();

    pending.next(listResponse);
    pending.complete();
    expect(component.selectedMembership()?.company.id).toBe(7);
  });
});
