import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DividerModule } from 'primeng/divider';
import { DatePickerModule } from 'primeng/datepicker';
import { InputNumberModule } from 'primeng/inputnumber';
import { MessageModule } from 'primeng/message';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ApiService } from '../core/api.service';
import { EventFilters, EventPageResponse, getApiErrorMessage } from '../core/api.models';

type TagSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast';

@Component({
  selector: 'app-events-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    AutoCompleteModule,
    ButtonModule,
    CardModule,
    DatePickerModule,
    DividerModule,
    InputNumberModule,
    MessageModule,
    SelectModule,
    TableModule,
    TagModule,
  ],
  templateUrl: './events-page.component.html',
  styleUrl: './events-page.component.scss',
})
export class EventsPageComponent {
  eventsResult?: EventPageResponse;
  apiError = '';
  descriptionSuggestions: string[] = [];

  eventType = '';
  description = '';
  dateFrom?: Date;
  dateTo?: Date;
  page = 1;
  pageSize = 50;

  readonly eventTypes = [
    { label: 'Inicio de sesion', value: 'user_login' },
    { label: 'Renovacion de token', value: 'token_renewal' },
    { label: 'Carga de CSV', value: 'csv_upload' },
    { label: 'Validacion de CSV', value: 'csv_validation' },
    { label: 'Carga de documento', value: 'doc_upload' },
    { label: 'Clasificacion con IA', value: 'ai_classification' },
    { label: 'Extraccion con IA', value: 'ai_extraction' },
    { label: 'Exportacion de eventos', value: 'event_export' },
    { label: 'Errores', value: 'error' },
  ];

  readonly descriptionCandidates = [
    'Archivo cargado',
    'Validacion de archivo',
    'Documento clasificado',
    'Datos extraidos',
    'Token renovado',
    'Error del sistema',
  ];

  constructor(private readonly api: ApiService) {}

  get eventsItems() {
    return this.eventsResult?.items ?? [];
  }

  loadEvents(): void {
    const filters: EventFilters = {
      event_type: this.eventType,
      description: this.description,
      date_from: this.dateFrom ? this.dateFrom.toISOString() : undefined,
      date_to: this.dateTo ? this.dateTo.toISOString() : undefined,
      page: this.page,
      page_size: this.pageSize,
    };

    this.api.listEvents(filters).subscribe({
      next: (response) => {
        if (!response.success || !response.data) {
          this.apiError = response.error?.message || 'Error al consultar eventos';
          return;
        }

        this.eventsResult = response.data;
        this.apiError = '';
      },
      error: (err) => {
        this.apiError = getApiErrorMessage(err, 'Error al consultar eventos');
      },
    });
  }

  exportEvents(): void {
    const filters: EventFilters = {
      event_type: this.eventType,
      description: this.description,
      date_from: this.dateFrom ? this.dateFrom.toISOString() : undefined,
      date_to: this.dateTo ? this.dateTo.toISOString() : undefined,
    };

    this.api.exportEvents(filters).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'eventos.xlsx';
        a.click();
        URL.revokeObjectURL(url);
      },
      error: (err) => {
        this.apiError = getApiErrorMessage(err, 'Error al exportar eventos');
      },
    });
  }

  filterDescription(event: { query: string }): void {
    const query = (event.query || '').toLowerCase();
    this.descriptionSuggestions = this.descriptionCandidates.filter((item) =>
      item.toLowerCase().includes(query),
    );
  }

  eventTypeLabel(type: string): string {
    return this.eventTypes.find((item) => item.value === type)?.label ?? type;
  }

  severityForEvent(type: string): TagSeverity {
    if (type === 'error') {
      return 'danger';
    }
    if (type.includes('ai')) {
      return 'contrast';
    }
    if (type.includes('csv')) {
      return 'info';
    }
    return 'success';
  }
}
