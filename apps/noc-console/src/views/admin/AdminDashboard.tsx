import React from 'react';
import { ServiceHealth } from '../../components/ServiceHealth';
import type { HealthResponse } from '../../types';
import { AdminUsers } from './AdminUsers';
import { AuditLog } from './AuditLog';
import { SystemSettings } from './SystemSettings';

/** Step 13b: the admin-only dashboard (users, audit log, system health and settings). */
export const AdminDashboard: React.FC<{
  currentUser: string;
  health?: HealthResponse;
  healthError: boolean;
}> = ({ currentUser, health, healthError }) => (
  <div className="space-y-4 lg:space-y-6" data-testid="admin-dashboard">
    <AdminUsers currentUser={currentUser} />
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-6">
      <div className="min-w-0 lg:col-span-8 lg:h-[560px]">
        <AuditLog />
      </div>
      <div className="flex min-w-0 flex-col gap-4 lg:col-span-4 lg:h-[560px] lg:gap-6">
        <div className="min-h-0 lg:max-h-[58%]">
          <SystemSettings />
        </div>
        <div className="min-h-0 lg:min-h-[200px] lg:flex-1">
          <ServiceHealth health={health} isError={healthError} />
        </div>
      </div>
    </div>
  </div>
);
