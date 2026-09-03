import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import {
  ElectronicTaxDocument,
  ElectronicTaxListResponse,
  FolioSummaryResponse,
} from './electronic-tax.models';
import { ElectronicTaxService } from './electronic-tax.service';

describe('ElectronicTaxService', () => {
  let service: ElectronicTaxService;
  let httpTesting: HttpTestingController;

  const document: ElectronicTaxDocument = {
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
    lines: [],
    references: [],
    events: [],
    exchange: null,
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(ElectronicTaxService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  it('lists documents using company and fiscal filters', () => {
    const response: ElectronicTaxListResponse = {
      documents: [document],
      pagination: { count: 1, page: 2, page_size: 10, total_pages: 2 },
    };

    service
      .listDocuments(7, {
        branch: 3,
        type_code: 33,
        state: 'READY',
        folio: 77,
        receiver_rut: ' 96543210-8 ',
        issue_date_from: '2026-09-01',
        issue_date_to: '2026-09-03',
        page: 2,
        page_size: 10,
      })
      .subscribe((result) => expect(result).toEqual(response));

    const request = httpTesting.expectOne(
      (candidate) => candidate.url === '/api/v1/electronic-tax-documents/',
    );
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('company')).toBe('7');
    expect(request.request.params.get('branch')).toBe('3');
    expect(request.request.params.get('type_code')).toBe('33');
    expect(request.request.params.get('state')).toBe('READY');
    expect(request.request.params.get('folio')).toBe('77');
    expect(request.request.params.get('receiver_rut')).toBe('96543210-8');
    expect(request.request.params.get('issue_date_from')).toBe('2026-09-01');
    expect(request.request.params.get('issue_date_to')).toBe('2026-09-03');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('10');
    request.flush(response);
  });

  it('creates a base DTE with an Idempotency-Key header', () => {
    service.createDocument(7, 31, 33, 'create-key').subscribe((result) => {
      expect(result.document).toEqual(document);
    });

    const request = httpTesting.expectOne('/api/v1/electronic-tax-documents/');
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('Idempotency-Key')).toBe('create-key');
    expect(request.request.body).toEqual({ company: 7, sale_id: 31, type_code: 33 });
    request.flush({ document, idempotent_replay: false });
  });

  it('validates and discards using the document version', () => {
    service.validateDocument(7, 9, 1, 'validate-key').subscribe();
    const validation = httpTesting.expectOne('/api/v1/electronic-tax-documents/9/validate/');
    expect(validation.request.body).toEqual({ company: 7, version: 1 });
    expect(validation.request.headers.get('Idempotency-Key')).toBe('validate-key');
    validation.flush({
      document: { ...document, state: 'READY', version: 2 },
      idempotent_replay: false,
    });

    service.discardDocument(7, 9, 2, 'discard-key').subscribe();
    const discard = httpTesting.expectOne('/api/v1/electronic-tax-documents/9/discard/');
    expect(discard.request.body).toEqual({ company: 7, version: 2 });
    expect(discard.request.headers.get('Idempotency-Key')).toBe('discard-key');
    discard.flush({
      document: { ...document, state: 'DISCARDED', version: 3 },
      idempotent_replay: false,
    });
  });

  it('creates credit and debit notes through explicit reference endpoints', () => {
    service
      .createCreditNote(
        7,
        9,
        { version: 4, reason: 'CANCEL_DOCUMENT', description: 'Anulación total' },
        'nc-key',
      )
      .subscribe();
    const credit = httpTesting.expectOne('/api/v1/electronic-tax-documents/9/credit-notes/');
    expect(credit.request.body).toEqual({
      company: 7,
      version: 4,
      reason: 'CANCEL_DOCUMENT',
      description: 'Anulación total',
    });
    expect(credit.request.headers.get('Idempotency-Key')).toBe('nc-key');
    credit.flush({ document: { ...document, id: 10, type_code: 61 }, idempotent_replay: false });

    service
      .createDebitNote(
        7,
        10,
        { version: 2, reason: 'CANCEL_CREDIT_NOTE', description: 'Anula NC' },
        'nd-key',
      )
      .subscribe();
    const debit = httpTesting.expectOne('/api/v1/electronic-tax-documents/10/debit-notes/');
    expect(debit.request.headers.get('Idempotency-Key')).toBe('nd-key');
    expect(debit.request.body.reason).toBe('CANCEL_CREDIT_NOTE');
    debit.flush({ document: { ...document, id: 11, type_code: 56 }, idempotent_replay: false });
  });

  it('loads folio availability without exposing CAF data', () => {
    const response: FolioSummaryResponse = {
      authorizations: [
        {
          type_code: 33,
          status: 'ACTIVE',
          start_folio: 1,
          end_folio: 100,
          next_folio: 8,
          available: 93,
        },
      ],
    };
    service.getFolioSummary(7).subscribe((result) => expect(result).toEqual(response));
    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/v1/folio-authorizations/summary/' &&
        candidate.params.get('company') === '7',
    );
    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('downloads the RIDE as a PDF blob in company scope', () => {
    service.downloadRide(7, 9).subscribe((blob) => expect(blob.type).toBe('application/pdf'));
    const request = httpTesting.expectOne(
      (candidate) =>
        candidate.url === '/api/v1/electronic-tax-documents/9/ride/' &&
        candidate.params.get('company') === '7',
    );
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['pdf'], { type: 'application/pdf' }));
  });
});
