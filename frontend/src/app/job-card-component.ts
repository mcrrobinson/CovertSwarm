import { Component, Input, Output, EventEmitter, NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-job-card',
  templateUrl: './job-card-component.html',
  styleUrl: './job-card-component.css',
  standalone: true,
  imports: [CommonModule]  // Import CommonModule here
})
export class JobCardComponent {
  @Input() job: { id: string; status: string } = { id: '', status: '' };
  @Output() statusChange = new EventEmitter<string>();
  baseURL: string = '/api';

  get jobStatus(): string {
    return this.job.status === 'Completed' ? 'Download' : this.job.status;
  }

  get downloadLink(): string {
    return this.job.status === 'Completed' ? `${this.baseURL}/job/download?uuid=${this.job.id}` : '';
  }

  ngOnChanges() {
    this.statusChange.emit(this.job.status);
  }
}
