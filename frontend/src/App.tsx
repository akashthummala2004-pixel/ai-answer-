import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ServerCrash } from 'lucide-react';
import { AppShell } from './components/layout/AppShell';
import { Button } from './components/ui/Button';
import { EmptyState, Spinner } from './components/ui/Feedback';
import { AppProvider, useApp } from './context/AppContext';
import { ThemeProvider } from './lib/theme';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import Login from './pages/Login';
import NewVerification from './pages/NewVerification';
import ReviewQueue from './pages/ReviewQueue';
import SettingsPage from './pages/Settings';
import VerificationDetail from './pages/VerificationDetail';

function Gate() {
  const { health, healthError, session, retryHealth } = useApp();

  if (healthError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <EmptyState
          icon={<ServerCrash className="h-8 w-8" />}
          title="Backend unavailable"
          description={`${healthError} Start it with: uvicorn app.main:app --port 8001`}
          action={<Button onClick={retryHealth}>Retry</Button>}
        />
      </div>
    );
  }
  if (!health) return <Spinner label="Connecting to verification service…" />;
  if (health.auth_required && !session) return <Login />;

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="verify" element={<NewVerification />} />
        <Route path="history" element={<History />} />
        <Route path="verifications/:id" element={<VerificationDetail />} />
        <Route path="review" element={<ReviewQueue />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppProvider>
        <BrowserRouter>
          <Gate />
        </BrowserRouter>
      </AppProvider>
    </ThemeProvider>
  );
}
