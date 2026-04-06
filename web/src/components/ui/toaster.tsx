import {
  Toast,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast"
import { useToast } from "@/hooks/use-toast"
import { CheckCircle2, XCircle, Info } from "lucide-react"

export function Toaster() {
  const { toasts } = useToast()

  return (
    <ToastProvider>
      {toasts.map(function ({ id, title, description, action, variant, ...props }) {
        // 根据变体选择图标
        const Icon = variant === 'success' 
          ? CheckCircle2 
          : variant === 'destructive' 
          ? XCircle 
          : Info;
        
        const iconColor = variant === 'success'
          ? 'text-green-600'
          : variant === 'destructive'
          ? 'text-red-600'
          : 'text-blue-600';

        return (
          <Toast key={id} variant={variant} {...props}>
            <div className="flex items-center gap-3 w-full">
              <Icon className={`w-5 h-5 flex-shrink-0 ${iconColor}`} />
              <div className="flex flex-col gap-0.5 flex-1">
                {title && <ToastTitle>{title}</ToastTitle>}
                {description && (
                  <ToastDescription>{description}</ToastDescription>
                )}
              </div>
            </div>
            {action}
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
