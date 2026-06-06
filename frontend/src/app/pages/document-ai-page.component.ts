import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { DividerModule } from 'primeng/divider';
import { FileUploadModule } from 'primeng/fileupload';
import { MessageModule } from 'primeng/message';
import { ProgressBarModule } from 'primeng/progressbar';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ApiService } from '../core/api.service';
import { AnalysisResultResponse, getApiErrorMessage } from '../core/api.models';

interface InvoiceItemView {
  quantity: number;
  name: string;
  unit_price: number;
  total: number;
}

interface InvoiceDataView {
  client_name: string;
  client_address: string;
  supplier_name: string;
  supplier_address: string;
  invoice_number: string;
  date: string;
  products: InvoiceItemView[];
  total: number;
}

interface InformationDataView {
  description: string;
  summary: string;
  sentiment: string;
}

@Component({
  selector: 'app-document-ai-page',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ButtonModule,
    CardModule,
    DividerModule,
    FileUploadModule,
    MessageModule,
    ProgressBarModule,
    TableModule,
    TagModule,
  ],
  templateUrl: './document-ai-page.component.html',
  styleUrl: './document-ai-page.component.scss',
})
export class DocumentAiPageComponent {
  documentFile?: File;
  analysisResult?: AnalysisResultResponse;
  apiError = '';

  constructor(private readonly api: ApiService) {}

  get isInvoice(): boolean {
    return this.analysisResult?.doc_type === 'invoice';
  }

  get isInformation(): boolean {
    return this.analysisResult?.doc_type === 'information';
  }

  get hasFallback(): boolean {
    return this.analysisResult?.fallback_used ?? (this.analysisResult?.ai_model?.includes('fallback') ?? false);
  }

  get fallbackReason(): string {
    return this.analysisResult?.fallback_reason || 'Sin detalle adicional';
  }

  get confidencePercent(): number {
    return Math.round((this.analysisResult?.confidence ?? 0) * 100);
  }

  get docTypeSeverity(): 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' {
    if (this.isInvoice) {
      return 'success';
    }
    if (this.isInformation) {
      return 'info';
    }
    return 'warn';
  }

  get invoiceData(): InvoiceDataView | null {
    if (!this.analysisResult?.extracted_data || !this.isInvoice) {
      return null;
    }
    return this.analysisResult.extracted_data as unknown as InvoiceDataView;
  }

  get informationData(): InformationDataView | null {
    if (!this.analysisResult?.extracted_data || !this.isInformation) {
      return null;
    }
    return this.analysisResult.extracted_data as unknown as InformationDataView;
  }

  onDocumentSelected(event: { files?: File[] }): void {
    this.documentFile = event.files?.[0];
  }

  analyzeDocument(): void {
    if (!this.documentFile) {
      this.apiError = 'Selecciona un documento';
      return;
    }

    this.api.analyzeDocument(this.documentFile).subscribe({
      next: (response) => {
        if (!response.success || !response.data) {
          this.apiError = response.error?.message || 'Error al analizar documento';
          return;
        }

        this.analysisResult = response.data;
        this.apiError = '';
      },
      error: (err) => {
        this.apiError = getApiErrorMessage(err, 'Error al analizar documento');
      },
    });
  }

  sentimentSeverity(sentiment: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' {
    const value = (sentiment || '').toLowerCase();
    if (value === 'positive') {
      return 'success';
    }
    if (value === 'negative') {
      return 'danger';
    }
    return 'secondary';
  }
}
