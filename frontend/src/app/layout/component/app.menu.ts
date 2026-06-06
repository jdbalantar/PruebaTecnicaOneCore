import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { PanelMenuModule } from 'primeng/panelmenu';

@Component({
  selector: 'app-menu',
  standalone: true,
  imports: [RouterModule, PanelMenuModule],
  template: `
    <p-panelMenu [model]="model" styleClass="layout-panel-menu"></p-panelMenu>
  `
})
export class AppMenu {
  model: MenuItem[] = [
    {
      label: 'Menu', icon: 'pi pi-fw pi-bars',
      expanded: true,
      items: [
        { label: 'Dashboard', icon: 'pi pi-home', routerLink: ['/app'] },
        { label: 'Upload CSV', icon: 'pi pi-upload', routerLink: ['/app/csv-upload'] },
        { label: 'Analisis IA', icon: 'pi pi-sparkles', routerLink: ['/app/document-ai'] },
        { label: 'Eventos', icon: 'pi pi-table', routerLink: ['/app/events'] },
        { label: 'Auth Refresh', icon: 'pi pi-refresh', routerLink: ['/app/auth-refresh'] }
      ]
    }
  ];
}
