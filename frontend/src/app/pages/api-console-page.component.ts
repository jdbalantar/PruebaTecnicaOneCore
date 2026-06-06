import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { RouterModule } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { MessageModule } from 'primeng/message';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { ProgressBarModule } from 'primeng/progressbar';
import { ApiService } from '../core/api.service';
import {
  EventFilters,
  EventPageResponse,
  SystemHealthResponse,
  getApiErrorMessage,
} from '../core/api.models';

type TagSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast';
type HealthStatus = 'up' | 'down' | undefined;

interface KpiItem {
  title: string;
  value: number;
  icon: string;
  color: TagSeverity;
}

interface NavigationCard {
  title: string;
  description: string;
  icon: string;
  route: string;
}

@Component({
  selector: 'app-api-console-page',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ButtonModule,
    CardModule,
    MessageModule,
    TagModule,
    ToolbarModule,
    ProgressBarModule
  ],
  templateUrl: './api-console-page.component.html',
  styleUrl: './api-console-page.component.scss'
})
export class ApiConsolePageComponent implements OnInit, OnDestroy {
  eventsResult?: EventPageResponse;
  systemHealth?: SystemHealthResponse;
  apiError = '';
  healthError = '';
  private healthTimer?: ReturnType<typeof setInterval>;
  private readonly eventTypeLabels: Record<string, string> = {
    user_login: 'Inicio de sesion',
    token_renewal: 'Renovacion de token',
    csv_upload: 'Carga de CSV',
    csv_validation: 'Validacion de CSV',
    doc_upload: 'Carga de documento',
    ai_classification: 'Clasificacion con IA',
    ai_extraction: 'Extraccion con IA',
    event_export: 'Exportacion de eventos',
    error: 'Error',
  };

  readonly navigationCards: NavigationCard[] = [
    {
      title: 'Carga de CSV',
      description: 'Carga y valida archivos CSV contra el backend.',
      icon: 'pi pi-upload',
      route: '/app/csv-upload'
    },
    {
      title: 'Analisis documental con IA',
      description: 'Sube PDF/JPG/PNG para clasificación y extracción.',
      icon: 'pi pi-sparkles',
      route: '/app/document-ai'
    },
    {
      title: 'Eventos',
      description: 'Consulta, filtra y exporta el histórico de eventos.',
      icon: 'pi pi-table',
      route: '/app/events'
    },
    {
      title: 'Renovar sesion',
      description: 'Renueva el token JWT con el endpoint protegido.',
      icon: 'pi pi-refresh',
      route: '/app/auth-refresh'
    }
  ];

  constructor(
    private readonly api: ApiService
  ) {}

  private get minioServiceStatus(): HealthStatus {
    return this.systemHealth?.services.minio?.status ?? this.systemHealth?.services.storage?.status;
  }

  private get s3ServiceStatus(): HealthStatus {
    return this.systemHealth?.services.s3?.status;
  }

  ngOnInit(): void {
    this.refreshSystemHealth();
    this.loadRecentEvents();
    this.healthTimer = setInterval(() => this.refreshSystemHealth(), 30000);
  }

  ngOnDestroy(): void {
    if (this.healthTimer) {
      clearInterval(this.healthTimer);
    }
  }

  loadRecentEvents(): void {
    const filters: EventFilters = {
      page: 1,
      page_size: 5
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
      }
    });
  }

  get eventsItems() {
    return this.eventsResult?.items ?? [];
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

  get integrationScore(): number {
    let score = 35;
    if (this.minioServiceStatus === 'up') {
      score += 10;
    }
    if (this.s3ServiceStatus === 'up') {
      score += 10;
    }
    if (this.systemHealth?.services.database.status === 'up') {
      score += 20;
    }
    if ((this.eventsResult?.items?.length || 0) > 0) {
      score += 15;
    }
    if (this.systemHealth?.status === 'ok') {
      score += 10;
    }
    return Math.min(score, 100);
  }

  get kpis(): KpiItem[] {
    const errorColor: TagSeverity = this.apiError ? 'danger' : 'secondary';

    return [
      {
        title: 'Eventos Consultados',
        value: this.eventsResult?.total ?? 0,
        icon: 'pi pi-table',
        color: 'info'
      },
      {
        title: 'MinIO',
        value: this.minioServiceStatus === 'up' ? 1 : 0,
        icon: 'pi pi-file',
        color: 'success'
      },
      {
        title: 'S3',
        value: this.s3ServiceStatus === 'up' ? 1 : 0,
        icon: 'pi pi-database',
        color: 'info'
      },
      {
        title: 'Base de datos',
        value: this.systemHealth?.services.database.status === 'up' ? 1 : 0,
        icon: 'pi pi-sparkles',
        color: 'contrast'
      },
      {
        title: 'Errores actuales',
        value: this.apiError ? 1 : 0,
        icon: 'pi pi-exclamation-triangle',
        color: errorColor
      }
    ];
  }

  recentEvents(limit = 5) {
    return this.eventsItems.slice(0, limit);
  }

  eventTypeLabel(type: string): string {
    return this.eventTypeLabels[type] ?? type;
  }

  systemStatusLabel(status: string | undefined): string {
    if (status === 'ok') {
      return 'Operativo';
    }
    if (status === 'degraded') {
      return 'Degradado';
    }
    return 'Sin datos';
  }

  serviceStatusLabel(status: 'up' | 'down' | undefined): string {
    return status === 'up' ? 'Operativo' : 'No disponible';
  }

  refreshSystemHealth(): void {
    this.api.getSystemHealth().subscribe({
      next: (response) => {
        if (!response.success || !response.data) {
          this.healthError = response.error?.message || 'No se pudo consultar el health del sistema';
          return;
        }

        this.systemHealth = response.data;
        this.healthError = '';
      },
      error: (err) => {
        this.healthError = getApiErrorMessage(err, 'No se pudo consultar el health del sistema');
      }
    });
  }

  healthSeverity(status: 'up' | 'down' | undefined): TagSeverity {
    return status === 'up' ? 'success' : 'danger';
  }

  dashboardStatus(): 'success' | 'warn' {
    return this.systemHealth?.status === 'ok' ? 'success' : 'warn';
  }
}
