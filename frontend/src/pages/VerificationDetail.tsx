import { Link, useParams } from 'react-router-dom';
import { LegacyDetail } from '../components/LegacyDetail';
import { SmartResult } from '../components/smart/SmartResult';
import { Button } from '../components/ui/Button';
import { Alert, Spinner } from '../components/ui/Feedback';
import type { SmartVerification, Verification } from '../lib/types';
import { useApi } from '../lib/useApi';

export default function VerificationDetail() {
  const { id } = useParams();
  const { data, setData, error, loading } = useApi<Verification | SmartVerification>(`/api/verifications/${id}`);

  if (loading && !data) return <Spinner label="Loading verification…" />;
  if (error || !data) {
    return (
      <Alert tone="error" title="Verification unavailable" action={<Link to="/history"><Button size="sm" variant="secondary">Back to history</Button></Link>}>
        {error ?? 'Not found.'}
      </Alert>
    );
  }
  if (data.version === 2) return <SmartResult record={data} setData={setData} />;
  return <LegacyDetail record={data} setData={setData} />;
}
