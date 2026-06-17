import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { MatchCardSkeletonComponent } from './match-card-skeleton.component';

describe('MatchCardSkeletonComponent', () => {
  let fixture: ComponentFixture<MatchCardSkeletonComponent>;
  let component: MatchCardSkeletonComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MatchCardSkeletonComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(MatchCardSkeletonComponent);
    component = fixture.componentInstance;
  });

  it('creates', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('renders the skeleton placeholders', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.card')).toBeTruthy();
    expect(fixture.nativeElement.querySelectorAll('.skel').length).toBeGreaterThan(0);
  });
});
