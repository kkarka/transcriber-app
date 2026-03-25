import { AlertTriangle } from "lucide-react";

interface ErrorDialogProps {
  message: string;
  onClose: () => void;
}

export function ErrorDialog({ message, onClose }: ErrorDialogProps) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/40 z-50">
      <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full shadow-lg">
        <div className="flex items-start gap-4">
          <AlertTriangle className="text-red-500 w-6 h-6" />

          <div className="flex-1">
            <h3 className="font-semibold mb-2">Upload Error</h3>

            <p className="text-muted-foreground text-sm">
              {message}
            </p>

            <button
              onClick={onClose}
              className="mt-4 px-4 py-2 bg-primary text-white rounded-md"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}