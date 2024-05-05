import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, timer } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';

@Injectable({
  providedIn: 'root',
})
export class ScanService {
  private baseURL: string = 'http://localhost:8000';
  results: any; // Declare the results property with a type

  constructor(private http: HttpClient) {}

  performScan(scanArguments: string): void {
    const headers = new HttpHeaders({ 'Authorization': 'Bearer someauthbearertoken' });

    // Start the job by sending scan arguments
    this.http.post<any>(`${this.baseURL}/job/create`, { args: scanArguments }, { headers })
      .subscribe(
        data => {
          this.results = data;  // Now 'results' is a declared property
          console.log('Job started successfully:', data);
          this.pollJobStatus(data);  // Assuming the job ID is returned in the response
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

  // Long polling function to check job status
  private pollJobStatus(jobId: string): void {
    const headers = new HttpHeaders({ 'Authorization': 'Bearer someauthbearertoken' });

    // Poll every 5 seconds
    const poll$ = timer(0, 1000).pipe(
      switchMap(() => this.http.get<any>(`${this.baseURL}/job/status?uuid=${jobId}`, { headers })),
      takeWhile(response => response !== 'Completed', true)
    );

    poll$.subscribe(
      response => {
        if (response === 'Completed') {
          this.addDownloadButton(jobId);
        } else {
            console.log('Job status:', response);
        }
      },
      error => {
        console.error('Error polling job status:', error);
      }
    );
  }
  private addDownloadButton(jobId: string): void {
    // Assuming there is a container div with id 'downloadButtonContainer' in your HTML
    const container = document.getElementById('dl');
    const button = document.createElement('button');
    button.innerText = 'Download Result';
    button.addEventListener('click', () => {
      window.location.href = `${this.baseURL}/job/download?uuid=${jobId}&token=someauthbearertoken`;
    });
    container?.appendChild(button);
  }
}

