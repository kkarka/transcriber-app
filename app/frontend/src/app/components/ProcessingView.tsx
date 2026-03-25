import { Loader2 } from "lucide-react";
import * as Progress from "@radix-ui/react-progress";
import { useState } from "react";

interface ProcessingViewProps {
  fileName: string;
  progress: number;
  stage: string;
  onCancel: () => void;
}

export function ProcessingView({ fileName, progress, stage, onCancel }: ProcessingViewProps) {

  const [cancelling, setCancelling] = useState(false);

  const handleCancelClick = async () => {
    setCancelling(true);
    await onCancel();
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="bg-card rounded-lg border border-border p-8 shadow-sm">

        <div className="text-center mb-8">
          <Loader2 className="w-16 h-16 mx-auto mb-4 text-primary animate-spin" />
          <h2 className="mb-2">Processing Your Video</h2>
          <p className="text-muted-foreground">{fileName}</p>
        </div>

        <div className="space-y-4">

          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">{stage}</span>
            <span className="text-muted-foreground">{progress}%</span>
          </div>

          <Progress.Root
            className="relative overflow-hidden bg-secondary rounded-full w-full h-3"
            value={progress}
          >
            <Progress.Indicator
              className="bg-primary h-full transition-transform duration-300 ease-out"
              style={{ transform: `translateX(-${100 - progress}%)` }}
            />
          </Progress.Root>

          <button
            disabled={cancelling || progress >= 100}
            onClick={handleCancelClick}
            className="w-full mt-6 px-4 py-2 border border-red-500 text-red-500 cursor-pointer rounded-lg hover:bg-red-500 hover:text-white transition-colors disabled:opacity-50"
          >
            {cancelling ? "Cancelling..." : "Cancel Processing"}
          </button>

          <p className="text-center text-muted-foreground mt-6">
            This may take a few moments. Please don't close this window.
          </p>

        </div>
      </div>
    </div>
  );
}