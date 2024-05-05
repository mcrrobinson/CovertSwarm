import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ScanService } from './services/scan.service';

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
  constructor(private http: HttpClient, private scanService: ScanService) {}

  startScan(scanArguments: string) {
    this.scanService.performScan(scanArguments);
  }

  ngOnInit() {
    this.getList();

    // Login
    this.http.post<any>('http://localhost:8000/login', { username: 'admin', password: 'admin' })
      .subscribe(
        data => {
          console.log('Login successful:', data);
        },
        error => {
          console.error('Failed to login:', error);
        }
      );
  }

  getList(): void {
    const headers = { 'Authorization': 'Bearer ' + "someauthbearertoken" };
    this.http.get<any>('http://localhost:8000/job/list', { headers })
      .subscribe(
        data => {
          console.log(data);
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
