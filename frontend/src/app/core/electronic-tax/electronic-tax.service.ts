import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  ElectronicTaxDetailResponse,
  ElectronicTaxListQuery,
  ElectronicTaxListResponse,
  ElectronicTaxMutationResponse,
  ElectronicTaxNoteRequest,
  ElectronicTaxTypeCode,
  FolioSummaryResponse,
} from './electronic-tax.models';

@Injectable({ providedIn: 'root' })
export class ElectronicTaxService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/electronic-tax-documents';

  listDocuments(
    companyId: number,
    query: ElectronicTaxListQuery = {},
  ): Observable<ElectronicTaxListResponse> {
    let params = new HttpParams().set('company', companyId.toString());

    if (query.branch) params = params.set('branch', query.branch.toString());
    if (query.type_code) params = params.set('type_code', query.type_code.toString());
    if (query.state) params = params.set('state', query.state);
    if (query.folio) params = params.set('folio', query.folio.toString());
    if (query.receiver_rut?.trim()) params = params.set('receiver_rut', query.receiver_rut.trim());
    if (query.issue_date_from) params = params.set('issue_date_from', query.issue_date_from);
    if (query.issue_date_to) params = params.set('issue_date_to', query.issue_date_to);
    params = params
      .set('page', (query.page ?? 1).toString())
      .set('page_size', (query.page_size ?? 20).toString());

    return this.http.get<ElectronicTaxListResponse>(`${this.baseUrl}/`, { params });
  }

  retrieveDocument(companyId: number, documentId: number): Observable<ElectronicTaxDetailResponse> {
    const params = new HttpParams().set('company', companyId.toString());
    return this.http.get<ElectronicTaxDetailResponse>(`${this.baseUrl}/${documentId}/`, { params });
  }

  createDocument(
    companyId: number,
    saleId: number,
    typeCode: Extract<ElectronicTaxTypeCode, 33 | 34>,
    idempotencyKey: string,
  ): Observable<ElectronicTaxMutationResponse> {
    return this.http.post<ElectronicTaxMutationResponse>(
      `${this.baseUrl}/`,
      { company: companyId, sale_id: saleId, type_code: typeCode },
      { headers: this.idempotencyHeaders(idempotencyKey) },
    );
  }

  validateDocument(companyId: number, documentId: number, version: number, idempotencyKey: string) {
    return this.mutate(
      `${this.baseUrl}/${documentId}/validate/`,
      companyId,
      version,
      idempotencyKey,
    );
  }

  discardDocument(companyId: number, documentId: number, version: number, idempotencyKey: string) {
    return this.mutate(
      `${this.baseUrl}/${documentId}/discard/`,
      companyId,
      version,
      idempotencyKey,
    );
  }

  issueDocument(companyId: number, documentId: number, version: number, idempotencyKey: string) {
    return this.mutate(`${this.baseUrl}/${documentId}/issue/`, companyId, version, idempotencyKey);
  }

  refreshStatus(companyId: number, documentId: number, version: number, idempotencyKey: string) {
    return this.mutate(
      `${this.baseUrl}/${documentId}/refresh-status/`,
      companyId,
      version,
      idempotencyKey,
    );
  }

  createCreditNote(
    companyId: number,
    documentId: number,
    request: ElectronicTaxNoteRequest,
    idempotencyKey: string,
  ): Observable<ElectronicTaxMutationResponse> {
    return this.http.post<ElectronicTaxMutationResponse>(
      `${this.baseUrl}/${documentId}/credit-notes/`,
      { company: companyId, ...request },
      { headers: this.idempotencyHeaders(idempotencyKey) },
    );
  }

  createDebitNote(
    companyId: number,
    documentId: number,
    request: ElectronicTaxNoteRequest,
    idempotencyKey: string,
  ): Observable<ElectronicTaxMutationResponse> {
    return this.http.post<ElectronicTaxMutationResponse>(
      `${this.baseUrl}/${documentId}/debit-notes/`,
      { company: companyId, ...request },
      { headers: this.idempotencyHeaders(idempotencyKey) },
    );
  }

  getFolioSummary(companyId: number): Observable<FolioSummaryResponse> {
    const params = new HttpParams().set('company', companyId.toString());
    return this.http.get<FolioSummaryResponse>('/api/v1/folio-authorizations/summary/', { params });
  }

  downloadRide(companyId: number, documentId: number): Observable<Blob> {
    const params = new HttpParams().set('company', companyId.toString());
    return this.http.get(`${this.baseUrl}/${documentId}/ride/`, { params, responseType: 'blob' });
  }

  private mutate(url: string, companyId: number, version: number, idempotencyKey: string) {
    return this.http.post<ElectronicTaxMutationResponse>(
      url,
      { company: companyId, version },
      { headers: this.idempotencyHeaders(idempotencyKey) },
    );
  }

  private idempotencyHeaders(key: string): HttpHeaders {
    return new HttpHeaders({ 'Idempotency-Key': key });
  }
}
