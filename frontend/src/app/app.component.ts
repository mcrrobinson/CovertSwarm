import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  results: any;
  scanArguments: string = '';
  constructor(private http: HttpClient) {}

  performScan(scanArguments: string): void {
    const headers = { 'Authorization': 'Bearer ' + "someauthbearertoken" };
    this.http.post<any>('http://localhost:8000/job/create', { args: scanArguments }, { headers })
      .subscribe(
        data => {
          this.results = data;
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
  
}
