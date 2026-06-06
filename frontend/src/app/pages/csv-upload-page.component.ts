import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { CheckboxModule } from 'primeng/checkbox';
import { DividerModule } from 'primeng/divider';
import { FileUploadModule } from 'primeng/fileupload';
import { MessageModule } from 'primeng/message';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ApiService } from '../core/api.service';
import { UploadResultResponse, getApiErrorMessage } from '../core/api.models';

@Component({
  selector: 'app-csv-upload-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    ButtonModule,
    CardModule,
    CheckboxModule,
    DividerModule,
    FileUploadModule,
    MessageModule,
    SelectModule,
    TableModule,
    TagModule,
  ],
  templateUrl: './csv-upload-page.component.html',
  styleUrl: './csv-upload-page.component.scss',
})
export class CsvUploadPageComponent {
  private readonly templatePath = 'assets/templates/onecore-csv-template.csv';

  validationMode = 'lenient';
  storageProvider = 'minio';
  allowDuplicates = false;
  csvFile?: File;
  csvResult?: UploadResultResponse;
  apiError = '';

  readonly validationOptions = [
    { label: 'Flexible', value: 'lenient' },
    { label: 'Estricta', value: 'strict' },
  ];

  readonly storageOptions = [
    { label: 'MinIO', value: 'minio' },
    { label: 'LocalStack S3', value: 'localstack' },
  ];

  constructor(private readonly api: ApiService) {}

  get statusSeverity(): 'success' | 'info' | 'warn' | 'danger' | 'secondary' | 'contrast' {
    if (this.csvResult?.status === 'completed') {
      return this.csvResult.error_rows > 0 ? 'warn' : 'success';
    }
    return 'info';
  }

  onCsvSelected(event: { files?: File[] }): void {
    this.csvFile = event.files?.[0];
  }

  downloadTemplate(): void {
    const anchor = document.createElement('a');
    anchor.href = this.templatePath;
    anchor.download = 'onecore-csv-template.csv';
    anchor.click();
  }

  uploadCsv(): void {
    if (!this.csvFile) {
      this.apiError = 'Selecciona un CSV';
      return;
    }

    this.api.uploadCsv(this.csvFile, this.validationMode, this.allowDuplicates, this.storageProvider).subscribe({
      next: (response) => {
        if (!response.success || !response.data) {
          this.apiError = response.error?.message || 'Error al subir CSV';
          return;
        }

        this.csvResult = response.data;
        this.apiError = '';
      },
      error: (err) => {
        this.apiError = getApiErrorMessage(err, 'Error al subir CSV');
      },
    });
  }
}
