import { Injectable } from '@angular/core';
import { Observable, Subject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class EventSourceService {
  private eventSource: EventSource | null = null;
  private messageSubject = new Subject<MessageEvent>();
  private openSubject = new Subject<Event>();
  private errorSubject = new Subject<Event>();

  public messages$: Observable<MessageEvent> = this.messageSubject.asObservable();
  public open$: Observable<Event> = this.openSubject.asObservable();
  public error$: Observable<Event> = this.errorSubject.asObservable();

  constructor() {}

  public connect(url: string): void {
    this.eventSource = new EventSource(url);
    this.eventSource.addEventListener('message', (event) => this.messageSubject.next(event));
    this.eventSource.addEventListener('open', (event) => this.openSubject.next(event));
    this.eventSource.addEventListener('error', (event) => this.errorSubject.next(event));
  }

  public disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}