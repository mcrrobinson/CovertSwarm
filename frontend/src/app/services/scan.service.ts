import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, timer } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';

@Injectable({
  providedIn: 'root',
})
export class ScanService {
  private baseURL: string = '/api';

  constructor(private http: HttpClient) {}

  performScan(scanArguments: string): void {
    const headers = new HttpHeaders({ 'Authorization': 'Bearer someauthbearertoken' });

    // Start the job by sending scan arguments
    this.http.post<any>(`${this.baseURL}/job/create`, { args: scanArguments }, { headers })
      .subscribe(
        data => {
          console.log('Job started successfully:', data);
        },
        error => {
          if (error.status === 403) {
            alert('Access Forbidden');
          } else {
            console.error('Failed to fetch results:', error);
          }
        }
      );
  }

  private addCard(jobId: string, status:string): void {

    const card = document.createElement('div');
    card.className = 'result-container';
    
    const name = document.createElement('div');
    name.className = 'result-name';
    name.innerText = jobId;
    card.appendChild(name);

    const link = document.createElement('a');
    link.id = jobId
    link.innerText = status;
    card.appendChild(link);

    const container = document.getElementById('dl');
    container?.appendChild(card);
  }
  private addDownloadButton(jobId: string): void {
    const element: HTMLAnchorElement | null = document.getElementById(jobId) as HTMLAnchorElement;
    if (element) {
      element.innerText = "Download";
      element.href = `${this.baseURL}/job/download?uuid=${jobId}`;
    }
  }
}

