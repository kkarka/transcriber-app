import { Download, Copy, CheckCircle2, RotateCcw, Sparkles, FileText } from 'lucide-react';
import { useState } from 'react';

interface TranscriptionResultProps {
  transcription: string;
  fileName: string;
  onStartOver: () => void;
}

export function TranscriptionResult({ transcription, fileName, onStartOver }: TranscriptionResultProps) {
  const [copiedRaw, setCopiedRaw] = useState(false);
  const [copiedNotes, setCopiedNotes] = useState(false);
  const [notes, setNotes] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  // --- REUSABLE COPY LOGIC ---
  const handleCopy = async (text: string, setCopiedIcon: (val: boolean) => void) => {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        setCopiedIcon(true);
        setTimeout(() => setCopiedIcon(false), 2000);
        return;
      } catch (err) { console.error("Copy failed", err); }
    }
    // Fallback for non-HTTPS
    const textArea = document.createElement("textarea");
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
    setCopiedIcon(true);
    setTimeout(() => setCopiedIcon(false), 2000);
  };

  // --- DOWNLOAD LOGIC ---
  const handleDownload = (text: string, suffix: string) => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_${suffix}.md`; // Download as Markdown
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleGenerateNotes = async () => {
    setIsGenerating(true);
    setNotes(""); 
    try {
      const response = await fetch("/api/v1/notes/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcription: transcription }),
      });
      if (!response.body) throw new Error("No response body");
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setNotes((prev) => prev + chunk);
      }
    } catch (error) {
      setNotes("Failed to generate notes. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-8">
      <div className="bg-card rounded-lg border border-border shadow-sm overflow-hidden">
        
        {/* --- RAW TRANSCRIPTION SECTION --- */}
        <div className="border-b border-border bg-accent/50 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-600" />
            <h2 className="font-semibold">Transcription</h2>
          </div>
          <div className="flex gap-2">
            <button onClick={() => handleCopy(transcription, setCopiedRaw)} className="p-2 cursor-pointer hover:bg-secondary rounded-md transition-colors">
              {copiedRaw ? <CheckCircle2 className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
            </button>
            <button onClick={() => handleDownload(transcription, "raw")} className="p-2 cursor-pointer hover:bg-secondary rounded-md transition-colors">
              <Download className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="p-6">
          <div className="bg-muted rounded-lg p-6 max-h-[300px] overflow-y-auto">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{transcription}</pre>
          </div>
        </div>

        {/* --- SMART NOTES SECTION --- */}
        <div className="border-t border-border bg-card p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-500" />
              Smart AI Notes
            </h3>
            
            <div className="flex gap-3">
              {/* Show Copy/Download only if notes exist */}
              {notes && !isGenerating && (
                <div className="flex gap-1 border-r border-border pr-3 mr-1">
                  <button 
                    onClick={() => handleCopy(notes, setCopiedNotes)} 
                    className="flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer hover:bg-accent rounded-md transition-colors"
                  >
                    {copiedNotes ? <CheckCircle2 className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedNotes ? "Copied" : "Copy Notes"}
                  </button>
                  <button 
                    onClick={() => handleDownload(notes, "notes")} 
                    className="flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer hover:bg-accent rounded-md transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download
                  </button>
                </div>
              )}
              
              <button
                onClick={handleGenerateNotes}
                disabled={isGenerating}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg cursor-pointer hover:opacity-90 disabled:opacity-50 text-sm font-medium transition-all shadow-sm"
              >
                {isGenerating ? "Generating..." : notes ? "Regenerate" : "Generate Notes"}
              </button>
            </div>
          </div>

          {(notes || isGenerating) && (
            <div className="bg-amber-50/30 dark:bg-amber-900/10 border border-amber-200/50 dark:border-amber-900/30 rounded-xl p-8 font-sans text-base leading-relaxed whitespace-pre-wrap shadow-inner min-h-[200px]">
              {notes}
              {isGenerating && <span className="animate-pulse inline-block w-2 h-5 bg-primary ml-1 align-middle rounded-full" />}
            </div>
          )}
        </div>

        {/* Footer Area */}
        <div className="border-t border-border px-6 py-4 bg-accent/10 flex justify-between items-center">
          <p className="text-xs text-muted-foreground italic">File: {fileName}</p>
          <button onClick={onStartOver} className="text-sm font-medium text-primary cursor-pointer hover:underline flex items-center gap-2">
            <RotateCcw className="w-4 h-4" />
            Transcribe Another Video
          </button>
        </div>
      </div>
    </div>
  );
}