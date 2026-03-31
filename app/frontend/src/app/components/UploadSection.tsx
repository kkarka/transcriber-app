import { useState, useRef } from "react";
import { Upload, FileVideo, AlertCircle } from "lucide-react";

interface UploadSectionProps {
  onStartTranscription: (source: "upload", data: File) => void;
  onError: (msg: string) => void;
}

export function UploadSection({ onStartTranscription, onError }: UploadSectionProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length) handleFile(files[0]);
  };

  const handleFile = (file: File) => {
    if (!file.type.startsWith("video/")) {
      onError("Please select a valid video file.");
      return;
    }
    // Size limit removed as requested!
    onStartTranscription("upload", file);
  };

  return (
    <div className="w-full max-w-3xl mx-auto mt-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="bg-card rounded-2xl shadow-sm border border-border overflow-hidden">
        <div className="p-8">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-semibold mb-2">Upload Video</h2>
            <p className="text-muted-foreground">Select a local video file from your device</p>
          </div>

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              relative group cursor-pointer
              border-2 border-dashed rounded-xl p-12
              transition-all duration-200 ease-in-out
              flex flex-col items-center justify-center
              ${isDragging 
                ? "border-primary bg-primary/5 scale-[0.99]" 
                : "border-border hover:border-primary/50 hover:bg-accent/50"}
            `}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              accept="video/*"
              onChange={(e) => {
                if (e.target.files?.length) handleFile(e.target.files[0]);
              }}
            />
            
            <div className={`p-4 rounded-full mb-4 transition-colors duration-200 ${isDragging ? "bg-primary/20" : "bg-secondary group-hover:bg-primary/10"}`}>
              <Upload className={`w-8 h-8 ${isDragging ? "text-primary" : "text-primary/70"}`} />
            </div>
            
            <h3 className="text-lg font-medium mb-1">
              Drag & drop your video here
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              or click to browse your files
            </p>
            
            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-background/50 px-3 py-1.5 rounded-full">
              <FileVideo className="w-3 h-3" />
              <span>Supports MP4, MOV, MKV, AVI, WEBM</span>
            </div>
          </div>

          <div className="mt-6 flex items-start gap-3 p-4 bg-accent/50 rounded-lg text-sm text-muted-foreground">
            <AlertCircle className="w-5 h-5 text-primary shrink-0 mt-0.5" />
            <p>
              Processing time depends on the length of your video. You can safely leave this tab open while we transcribe.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}