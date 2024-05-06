import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ScanService } from './services/scan.service';
import { CommonModule } from '@angular/common';
import { switchMap, takeWhile, timer } from 'rxjs';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ErrorDialogComponent } from './error-dialog.component';


@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, FormsModule, CommonModule, MatDialogModule ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  baseURL: string = '/api';
  scanArguments: string = '';
  MAX_ARG_LENGTH = 1000; // Maximum allowed argument length

  constructor(private http: HttpClient, private scanService: ScanService, public dialog: MatDialog) {}

  startScan(scanArguments: string) {
    try {
      this.validateArguments(scanArguments);
      this.scanService.performScan(scanArguments);
      this.scanArguments = ''; // Reset the input field
    } catch (error) {
      this.dialog.open(ErrorDialogComponent, {
        data: { message: error }
      });
    }
  }

  ngOnInit() {
    this.getList();
  }

  getList(): void {
    this.http.get<any>('/api/job/list')
      .subscribe((data) => {
        data.forEach((result: { uuid: string; status: string }) => {
          this.addCard(result.uuid, result.status);
          this.pollJobStatus(result.uuid);
        });       
      });

  }

  validateArguments(arg: string): void {
    const disallowedChars = ["&", "|", ";", "$", ">", "<", "`", "\\", "!"];
    const disallowedCharsUsed = disallowedChars.filter(char => arg.includes(char));

    if(arg.length === 0) {
      throw new Error("You can't leave the argument empty");
    }

    if (disallowedCharsUsed.length > 0) {
      throw new Error(`Disallowed character(s) '${disallowedCharsUsed.join(", ")}' in argument`);
    }

    if (arg.length > this.MAX_ARG_LENGTH) {
      throw new Error(`Argument too long, max ${this.MAX_ARG_LENGTH} characters`);
    }

    if (arg.startsWith("file://")) {
      throw new Error("Illegal protocol used in argument");
    }
  }

  // Long polling function to check job status
  pollJobStatus(jobId: string): void {
    // Poll every 5 seconds
    const poll$ = timer(0, 1000).pipe(
      switchMap(() => this.http.get<any>(`${this.baseURL}/job/status?uuid=${jobId}`)),
      takeWhile(response => response !== 'Completed', true)
    );

    poll$.subscribe(
      response => {
        if (response === 'Completed') {
          this.addDownloadButton(jobId);
        } else {
            console.log('Job status:', response);
            const element = document.getElementById(jobId);
            if (element) {
                element.innerText = response;
            }
        }
      },
      error => {
        console.error('Error polling job status:', error);
      }
    );
  }

  addCard(jobId: string, status:string): void {

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

  deleteAll(): void {
    this.http.delete<any>('/api/jobs')
      .subscribe((data) => {
        const container = document.getElementById('dl');
        if (container) {
          container.innerHTML = '';
        }

        // Now add the remaining cards
        data.forEach((result: { uuid: string; status: string }) => {
          this.addCard(result.uuid, result.status);
          this.pollJobStatus(result.uuid);
        }); 
      });
  }
  
}
