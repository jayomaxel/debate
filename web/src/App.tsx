import AppRouter from '@/components/app-router';
import { AuthProvider } from '@/store/auth.context';
import { Toaster } from '@/components/ui/toaster';

function App() {
  return (
    <AuthProvider>
      <AppRouter />
      <Toaster />
    </AuthProvider>
  );
}

export default App;
