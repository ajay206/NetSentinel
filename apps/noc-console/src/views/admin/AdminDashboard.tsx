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
  <div className="space-y-4" data-testid="admin-dashboard">
    <AdminUsers currentUser={currentUser} />
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="lg:col-span-8 lg:h-[480px]">
        <AuditLog />
      </div>
      <div className="flex flex-col gap-4 lg:col-span-4">
        <SystemSettings />
        <div className="lg:h-[300px]">
          <ServiceHealth health={health} isError={healthError} />
        </div>
      </div>
    </div>
  </div>
);
