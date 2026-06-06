import { Routes } from '@angular/router';
import { AppLayout } from './layout/component/app.layout';
import { authGuard } from './core/auth.guard';
import { guestGuard } from './core/guest.guard';
import { ApiConsolePageComponent } from './pages/api-console-page.component';
import { AuthRefreshPageComponent } from './pages/auth-refresh-page.component';
import { CsvUploadPageComponent } from './pages/csv-upload-page.component';
import { DocumentAiPageComponent } from './pages/document-ai-page.component';
import { EventsPageComponent } from './pages/events-page.component';
import { LoginPageComponent } from './pages/login-page.component';

export const routes: Routes = [
	{ path: 'login', component: LoginPageComponent, canActivate: [guestGuard] },
	{
		path: '',
		component: AppLayout,
		canActivate: [authGuard],
		canActivateChild: [authGuard],
		children: [
			{ path: 'app', component: ApiConsolePageComponent },
			{ path: 'app/csv-upload', component: CsvUploadPageComponent },
			{ path: 'app/document-ai', component: DocumentAiPageComponent },
			{ path: 'app/events', component: EventsPageComponent },
			{ path: 'app/auth-refresh', component: AuthRefreshPageComponent },
			{ path: '', pathMatch: 'full', redirectTo: 'app' }
		]
	},
	{ path: '**', redirectTo: 'app' }
];
