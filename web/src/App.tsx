import AppRouter from '@/components/app-router';
import { RouterProvider } from '@/lib/router';
import { AuthProvider } from '@/store/auth.context';
import { Toaster } from '@/components/ui/toaster';

function App() {
  return (
    <AuthProvider>
      <RouterProvider>
        <AppRouter />
        <Toaster />
      </RouterProvider>
    </AuthProvider>
  );
}

export default App;
