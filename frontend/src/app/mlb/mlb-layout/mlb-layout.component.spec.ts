import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { MlbLayoutComponent } from './mlb-layout.component';

describe('MlbLayoutComponent', () => {
  let fixture: ComponentFixture<MlbLayoutComponent>;
  let component: MlbLayoutComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MlbLayoutComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(MlbLayoutComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('creates the layout', () => {
    expect(component).toBeTruthy();
  });

  it('defaults the active tab index to 0', () => {
    expect(component.activeIndex()).toBe(0);
  });

  it('renders a router-outlet', () => {
    const outlet = fixture.nativeElement.querySelector('router-outlet');
    expect(outlet).not.toBeNull();
  });

  it('updates the active index from a navigated url', () => {
    const update = (component as unknown as {
      updateIndex: (url: string) => void;
    }).updateIndex.bind(component);

    update('/mlb/history');
    expect(component.activeIndex()).toBe(3);

    update('/mlb/tomorrow');
    expect(component.activeIndex()).toBe(1);

    update('/mlb/unknown');
    expect(component.activeIndex()).toBe(0);
  });
});
