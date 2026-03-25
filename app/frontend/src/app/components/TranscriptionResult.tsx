import { Download, Copy, CheckCircle2, RotateCcw } from 'lucide-react';
import { useState } from 'react';

interface TranscriptionResultProps {
  transcription: string;
  fileName: string;
  onStartOver: () => void;
}

export function TranscriptionResult({ transcription, fileName, onStartOver }: TranscriptionResultProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(transcription);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([transcription], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_transcription.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full max-w-5xl mx-auto">
      <div className="bg-card rounded-lg border border-border shadow-sm overflow-hidden">
        <div className="border-b border-border bg-accent/50 px-6 py-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              <h2>Transcription Complete</h2>
            </div>
            <p className="text-muted-foreground">{fileName}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCopy}
              className="px-4 py-2 bg-secondary cursor-pointer text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors flex items-center gap-2"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>
            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg cursor-pointer hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Download
            </button>
          </div>
        </div>

        <div className="p-6">
          <div className="bg-muted rounded-lg p-6 max-h-[600px] overflow-y-auto">
            <pre className="whitespace-pre-wrap font-mono text-sm text-foreground">
              {transcription}
            </pre>
          </div>
        </div>

        <div className="border-t border-border px-6 py-4 bg-accent/30">
          <button
            onClick={onStartOver}
            className="px-6 py-2 text-primary hover:bg-accent cursor-pointer rounded-lg transition-colors flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Transcribe Another Video
          </button>
        </div>
      </div>
    </div>
  );
}
