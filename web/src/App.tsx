import AppRouter from '@/components/app-router';
import { RouterProvider } from '@/lib/router';
import { AuthProvider } from '@/store/auth.context';
import { Toaster } from '@/components/ui/toaster';
import ErrorBoundary from '@/components/error-boundary';

function App() {
  return (
    <AuthProvider>
      <RouterProvider>
        <ErrorBoundary><AppRouter /></ErrorBoundary>
        <Toaster />
      </RouterProvider>
    </AuthProvider>
  );
}

export default App;
