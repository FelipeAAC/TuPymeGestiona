import { provideHttpClient } from '@angular/common/http';
import { bootstrapApplication } from '@angular/platform-browser';

import { MaintainersApp } from './app/app';

bootstrapApplication(MaintainersApp, {
  providers: [provideHttpClient()],
}).catch((error: unknown) => console.error(error));
