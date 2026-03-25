import { Upload, Link2 } from "lucide-react";
import { useState } from "react";

interface UploadSectionProps {
  onStartTranscription: (source: "upload" | "youtube", data: File | string) => void;
  onError: (message: string) => void;
}

const allowedTypes = [
  "video/mp4",
  "video/quicktime",
  "video/x-matroska",
  "video/x-msvideo",
  "video/webm",
];

export function validateVideo(file: File) {
  if (!allowedTypes.includes(file.type)) {
    return "Unsupported file format. Please upload MP4, MOV, MKV, AVI, or WEBM.";
  }

  if (file.size > 500 * 1024 * 1024) {
    return "File is too large. Maximum allowed size is 500MB.";
  }

  return null;
}

function isValidYoutubeUrl(url: string) {
  const regex =
    /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|shorts\/)|youtu\.be\/)[A-Za-z0-9_-]{11}/;

  return regex.test(url);
}

function getYoutubeId(url: string) {
  const match = url.match(
    /(?:youtube\.com\/watch\?v=|youtube\.com\/shorts\/|youtu\.be\/)([A-Za-z0-9_-]{11})/
  );

  return match ? match[1] : null;
}

export function UploadSection({ onStartTranscription, onError }: UploadSectionProps) {
  const [activeTab, setActiveTab] = useState<"upload" | "youtube">("upload");

  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubeThumbnail, setYoutubeThumbnail] = useState<string | null>(null);
  const [youtubeTitle, setYoutubeTitle] = useState<string | null>(null);
  const [youtubeChannel, setYoutubeChannel] = useState<string | null>(null);
  const [youtubeDuration, setYoutubeDuration] = useState<string | null>(null);
  const [youtubeLoading, setYoutubeLoading] = useState(false);

  const [dragActive, setDragActive] = useState(false);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const handleFile = (file: File) => {
    const error = validateVideo(file);

    if (error) {
      onError(
        `"${file.name}" is not a supported video format. Please upload MP4, MOV, MKV, AVI, or WEBM files under 500MB.`
      );
      return;
    }

    setVideoFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const startUpload = () => {
    if (videoFile) {
      onStartTranscription("upload", videoFile);
    }
  };

  const handleYoutubeSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!isValidYoutubeUrl(youtubeUrl)) {
      onError("Please enter a valid YouTube URL");
      return;
    }

    onStartTranscription("youtube", youtubeUrl);
  };

  const handleYoutubeChange = async (url: string) => {
    setYoutubeUrl(url);

    const id = getYoutubeId(url);

    if (!id) {
      setYoutubeThumbnail(null);
      setYoutubeTitle(null);
      setYoutubeChannel(null);
      setYoutubeDuration(null);
      return;
    }

    setYoutubeLoading(true);

    try {
      const thumbnail = `https://img.youtube.com/vi/${id}/maxresdefault.jpg`;
      setYoutubeThumbnail(thumbnail);

      const metaRes = await fetch(
        `https://www.youtube.com/oembed?url=${url}&format=json`
      );
      const meta = await metaRes.json();

      setYoutubeTitle(meta.title);
      setYoutubeChannel(meta.author_name);

      const durRes = await fetch(`https://noembed.com/embed?url=${url}`);
      const durData = await durRes.json();

      if (durData.duration) {
        const minutes = Math.floor(durData.duration / 60);
        const seconds = durData.duration % 60;
        setYoutubeDuration(`${minutes}:${seconds.toString().padStart(2, "0")}`);
      }
    } catch (err) {
      console.error("YouTube metadata fetch failed", err);
    }

    setYoutubeLoading(false);
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      <div className="bg-card rounded-lg border border-border p-8 shadow-sm">

        <div className="flex gap-2 mb-6 border-b border-border">

          <button
            onClick={() => setActiveTab("upload")}
            className={`px-6 py-3 transition-colors cursor-pointer relative ${
              activeTab === "upload"
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Upload className="inline-block w-5 h-5 mr-2 " />
            Upload Video
          </button>

          <button
            onClick={() => setActiveTab("youtube")}
            className={`px-6 py-3 cursor-pointer transition-colors relative ${
              activeTab === "youtube"
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Link2 className="inline-block w-5 h-5 mr-2 " />
            YouTube URL
          </button>

        </div>

        {activeTab === "upload" ? (
          <div>

            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
                dragActive
                  ? "border-primary bg-accent"
                  : "border-border hover:border-primary/50"
              }`}
            >

              <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />

              <h3 className="mb-2">Drop your video here</h3>

              <p className="text-muted-foreground mb-4">
                or click to browse
              </p>

              <input
                type="file"
                id="video-upload"
                accept="video/mp4,video/webm,video/quicktime,video/x-matroska,video/x-msvideo"
                onChange={handleFileChange}
                className="hidden"
              />

              <label
                htmlFor="video-upload"
                className="inline-block px-6 py-3 bg-primary text-primary-foreground rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
              >
                Choose File
              </label>

            </div>

            {previewUrl && (
              <div className="mt-6 border border-border rounded-lg p-4">

                <video src={previewUrl} controls className="w-full rounded-md" />

                <div className="mt-3 text-sm text-muted-foreground">
                  <p><strong>File:</strong> {videoFile?.name}</p>
                  <p>
                    <strong>Size:</strong>{" "}
                    {videoFile
                      ? (videoFile.size / (1024 * 1024)).toFixed(2) + " MB"
                      : ""}
                  </p>
                </div>

                <div className="flex gap-3 mt-4">

                  <button
                    onClick={() => {
                      setVideoFile(null);
                      setPreviewUrl(null);
                    }}
                    className="flex-1 px-6 py-3 border border-border rounded-lg hover:bg-accent cursor-pointer"
                  >
                    Remove Video
                  </button>

                  <button
                    onClick={startUpload}
                    className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
                  >
                    Start Transcription
                  </button>

                </div>

              </div>
            )}

          </div>
        ) : (

          <form onSubmit={handleYoutubeSubmit} className="space-y-4">

            <input
              type="url"
              value={youtubeUrl}
              onChange={(e) => handleYoutubeChange(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              className="w-full px-4 py-3 border border-border rounded-lg"
              required
            />

            {youtubeLoading && (
              <div className="mt-6 border border-border rounded-lg p-4 animate-pulse">
                <div className="w-full h-48 bg-muted rounded-md"></div>
              </div>
            )}

            {youtubeThumbnail && !youtubeLoading && (
              <div className="mt-6 border border-border rounded-lg p-4">

                <img
                  src={youtubeThumbnail}
                  alt="YouTube Thumbnail"
                  className="w-full rounded-md"
                />

                <div className="mt-3">

                  {youtubeTitle && <p className="font-semibold">{youtubeTitle}</p>}
                  {youtubeChannel && (
                    <p className="text-sm text-muted-foreground">
                      Channel: {youtubeChannel}
                    </p>
                  )}
                  {youtubeDuration && (
                    <p className="text-sm text-muted-foreground">
                      Duration: {youtubeDuration}
                    </p>
                  )}

                </div>

                <div className="flex gap-3 mt-4">

                  <button
                    type="button"
                    onClick={() => {
                      setYoutubeUrl("");
                      setYoutubeThumbnail(null);
                      setYoutubeTitle(null);
                      setYoutubeChannel(null);
                      setYoutubeDuration(null);
                    }}
                    className="flex-1 px-6 py-3 border border-border rounded-lg cursor-pointer hover:bg-accent"
                  >
                    Remove Video
                  </button>

                  <button
                    type="submit"
                    className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
                  >
                    Start Transcription
                  </button>

                </div>

              </div>
            )}

          </form>
        )}
      </div>
    </div>
  );
}