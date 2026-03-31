import { useState, useRef, useEffect } from "react";
import { FileVideo, Loader2 } from "lucide-react";
import { UploadSection } from "./components/UploadSection";
import { ProcessingView } from "./components/ProcessingView";
import { TranscriptionResult } from "./components/TranscriptionResult";
import { ErrorDialog } from "./components/ErrorDialog";
import { uploadVideo, checkStatus, cancelJob } from "../api/transcription";

type AppState = "upload" | "processing" | "result";

export default function App() {
  const [state, setState] = useState<AppState>("upload");
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [fileName, setFileName] = useState("");
  const [transcription, setTranscription] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [displayProgress, setDisplayProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState("");
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  
  // Video Preview State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Generate the preview URL whenever a new file is locked in
  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);

    // Clean up memory
    return () => URL.revokeObjectURL(objectUrl);
  }, [selectedFile]);

  const handleStartTranscription = async (
    source: "upload",
    data: File
  ) => {
    setProgress(0);
    setDisplayProgress(0);
    setStage("Preparing video...");

    const allowedTypes = [
      "video/mp4",
      "video/quicktime",
      "video/x-matroska",
      "video/x-msvideo",
      "video/webm"
    ];

    if (!allowedTypes.includes(data.type)) {
      setError("Unsupported file format. Please upload MP4, MOV, MKV, AVI, or WEBM.");
      return;
    }

    setFileName(data.name);
    setSelectedFile(data); // Lock in the file for the video preview

    try {
      const job = await uploadVideo(data);
      setJobId(job.job_id);
      setState("processing");
      pollStatus(job.job_id);
    } catch (err) {
      console.error("Upload failed", err);
      setError("Upload failed. Please try again.");
    }
  };

  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayProgress((prev) => {
        if (prev >= progress) return prev;
        return prev + 1;
      });
    }, 30);

    return () => clearInterval(interval);
  }, [progress]);

  const pollStatus = (jobId: string) => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    pollingRef.current = setInterval(async () => {
      try {
        const status = await checkStatus(jobId);

        if (status.progress !== undefined) {
          setProgress(status.progress);
        }

        setStage(status.stage || "");

        if (status.status.toLowerCase() === "completed" || status.progress === 100) {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setProgress(100);
          setIsFinalizing(true);

          const finalText = status.transcription || status.result || status.text || "Transcription completed, but no text was returned.";

          setTimeout(() => {
            setTranscription(finalText);
            setState("result");
          }, 1500);
        }

        if (status.status === "failed") {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setError("Transcription failed. Please try again.");
          setState("upload");
          setSelectedFile(null);
        }
      } catch (error) {
        console.error("Polling error:", error);
        setError("Network error while checking transcription status.");
      }
    }, 3000);
  };

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  const handleStartOver = () => {
    setState("upload");
    setFileName("");
    setTranscription("");
    setJobId(null);
    setProgress(0);
    setIsFinalizing(false);
    setSelectedFile(null); // Clear preview

    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }
  };

  const handleCancel = async () => {
    if (!jobId) return;

    await cancelJob(jobId);

    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    setState("upload");
    setProgress(0);
    setIsFinalizing(false);
    setSelectedFile(null); // Clear preview
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b border-border bg-card">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center gap-3">
            <FileVideo className="w-8 h-8 text-primary" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Video Transcription</h1>
              <p className="text-muted-foreground">
                Upload a video to get instant transcription notes
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12 flex-grow w-full">
        
        {/* Render the Video Preview when processing or viewing results */}
        {previewUrl && state !== "upload" && (
          <div className="mb-8 flex justify-center animate-in fade-in duration-500">
            <div className="rounded-xl overflow-hidden border border-border shadow-sm max-w-3xl w-full bg-black">
              <video
                src={previewUrl}
                controls
                className="w-full h-auto max-h-[400px] object-contain"
              >
                Your browser does not support the video tag.
              </video>
            </div>
          </div>
        )}

        {state === "upload" && (
          <UploadSection 
            onStartTranscription={handleStartTranscription} 
            onError={(msg) => setError(msg)} 
          />
        )}

        {state === "processing" && !isFinalizing && (
          <ProcessingView
            fileName={fileName}
            progress={displayProgress}
            stage={stage}
            onCancel={handleCancel}
          />
        )}
        
        {state === "processing" && isFinalizing && (
          <div className="flex flex-col items-center justify-center py-24 space-y-4 animate-in fade-in duration-500">
            <Loader2 className="w-12 h-12 text-primary animate-spin" />
            <h2 className="text-xl font-semibold">Finalizing Transcription...</h2>
            <p className="text-muted-foreground">Formatting your text for display</p>
          </div>
        )}

        {state === "result" && (
          <TranscriptionResult
            transcription={transcription}
            fileName={fileName}
            onStartOver={handleStartOver}
          />
        )}
      </main>

      <footer className="border-t border-border mt-auto py-6">
        <div className="max-w-7xl mx-auto px-6 text-center text-muted-foreground">
          <p>
            Powered by AI transcription technology. Developed by Arka.
          </p>
        </div>
      </footer>

      {error && (
        <ErrorDialog
          message={error}
          onClose={() => setError(null)}
        />
      )}
    </div>
  );
}