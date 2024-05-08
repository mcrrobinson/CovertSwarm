import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ScanService } from './services/scan.service';
import { CommonModule } from '@angular/common';
import { Subscription, switchMap, takeWhile, timer } from 'rxjs';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { ErrorDialogComponent } from './error-dialog.component';
import { EventSourceService } from './event-source.service';


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
  private subscriptions: Subscription[] = [];

  constructor(private http: HttpClient, private scanService: ScanService, public dialog: MatDialog, private eventSourceService: EventSourceService) {}

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

    let url = '/api/subscribe';
    this.eventSourceService.connect(url);

    const messageSubscription = this.eventSourceService.messages$.subscribe((event) => {
      try {
        const parsedData = JSON.parse(event.data);
        switch (parsedData.task) {
          case "create":
            this.addCard(parsedData.uuid, parsedData.status);
            break;
          case "update":
            this.updateCard(parsedData.uuid, parsedData.status);
            break;
          case "delete":
            this.deleteCard(parsedData.uuid);
            break;
          default:
            console.error('Unknown task:', parsedData.task);
            break;
        }
        // this.updateCard(parsedData.uuid, parsedData.status);
      } catch (error) {
        console.error('Failed to parse event data:', error);
      }
    });
    this.subscriptions.push(messageSubscription);

    const openSubscription = this.eventSourceService.open$.subscribe((event) => {
      console.log('open', event);
    });
    this.subscriptions.push(openSubscription);

    const errorSubscription = this.eventSourceService.error$.subscribe((event) => {
      console.log('error', event);
    });
    this.subscriptions.push(errorSubscription);
  }

  getList(): void {
    this.http.get<any>('/api/job/list')
      .subscribe((data) => {
        data.forEach((result: { uuid: string; status: string }) => {
          this.addCard(result.uuid, result.status);
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

  updateCard(jobId: string, status:string): void {
    const element = document.getElementById(jobId + '-status');
    if (element) {
      element.innerText = status;
      if (status === 'Completed') {
        this.addDownloadButton(jobId);
      }
    }
  }

  deleteCard(jobId: string): void {
    const element = document.getElementById(jobId);
    if (element) {
      element.parentNode?.removeChild(element);
    }
  }

  addCard(jobId: string, status:string): void {

    const card = document.createElement('div');
    card.id = jobId;
    card.className = 'result-container';
    
    const name = document.createElement('div');
    name.className = 'result-name';
    name.innerText = jobId;
    card.appendChild(name);

    const link = document.createElement('a');
    link.id = jobId + '-status';
    link.innerText = status;

    if (status === 'Completed') {
      link.innerText = "Download";
      link.href = `${this.baseURL}/job/download?uuid=${jobId}`;
    }
    card.appendChild(link);

    const container = document.getElementById('dl');
    container?.appendChild(card);
  }

  private addDownloadButton(jobId: string): void {
    const element: HTMLAnchorElement | null = document.getElementById(jobId + '-status') as HTMLAnchorElement;
    if (element) {
      element.innerText = "Download";
      element.href = `${this.baseURL}/job/download?uuid=${jobId}`;
    }
  }

  deleteAll(): void {
    this.http.delete<any>('/api/jobs')
      .subscribe((data) => {
        console.log('All jobs deleted:', data);
      });
  }
  
}
