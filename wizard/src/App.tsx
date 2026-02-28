import { Routes, Route } from 'react-router-dom';
import { WizardProvider, useWizard } from './state/context';
import { WizardShell } from './components/layout/WizardShell';
import {
  StepWelcome,
  StepHardware,
  StepPlatform,
  StepDeployment,
  StepLLM,
  StepModels,
  StepSecurity,
  StepStorage,
  StepGateway,
  StepChannels,
  StepReview,
  StepDeploy,
} from './components/steps';
import { DashboardShell } from './components/dashboard/DashboardShell';
import { OverviewPage } from './components/dashboard/OverviewPage';
import { AgentsPage } from './components/dashboard/AgentsPage';
import { ModelsPage } from './components/dashboard/ModelsPage';
import { SecurityPage } from './components/dashboard/SecurityPage';
import { ChannelsPage } from './components/dashboard/ChannelsPage';
import { LogsPage } from './components/dashboard/LogsPage';
import { SettingsPage } from './components/dashboard/SettingsPage';
import { TriggersPage } from './components/dashboard/TriggersPage';
import { InstancesPage } from './components/dashboard/InstancesPage';
import { DataManagementPage } from './components/dashboard/DataManagementPage';

const STEP_COMPONENTS = [
  StepWelcome,
  StepHardware,
  StepPlatform,
  StepDeployment,
  StepLLM,
  StepModels,
  StepSecurity,
  StepStorage,
  StepGateway,
  StepChannels,
  StepReview,
  StepDeploy,
];

function WizardContent() {
  const { state } = useWizard();
  const StepComponent = STEP_COMPONENTS[state.currentStep];
  if (!StepComponent) return null;
  return (
    <WizardShell>
      <StepComponent />
    </WizardShell>
  );
}

function WizardPage() {
  return (
    <WizardProvider>
      <WizardContent />
    </WizardProvider>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<WizardPage />} />
      <Route path="/dashboard" element={<DashboardShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="security" element={<SecurityPage />} />
        <Route path="triggers" element={<TriggersPage />} />
        <Route path="instances" element={<InstancesPage />} />
        <Route path="channels" element={<ChannelsPage />} />
        <Route path="data" element={<DataManagementPage />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
