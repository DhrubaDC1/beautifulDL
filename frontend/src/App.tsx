import { useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

interface VideoFormat {
  format_id: string;
  format_note: string;
  ext: string;
  resolution: string;
  filesize: number | null;
  acodec: string;
  vcodec: string;
}

interface VideoInfo {
  id: string;
  title: string;
  thumbnail: string;
  duration: number;
  uploader: string;
  formats: VideoFormat[];
}

function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<string>("best");
  const [downloading, setDownloading] = useState(false);

  const fetchVideoInfo = async () => {
    if (!url.trim()) {
      setError("Please enter a YouTube URL");
      return;
    }

    setLoading(true);
    setError(null);
    setVideoInfo(null);

    try {
      const response = await fetch(`${API_BASE}/api/info?url=${encodeURIComponent(url)}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to fetch video info");
      }

      setVideoInfo(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const [downloadProgress, setDownloadProgress] = useState<{
    percent: number;
    speed: number;
    eta: number;
    status: string;
  } | null>(null);

  const formatSpeed = (speed: number) => {
    if (!speed) return "0 MB/s";
    const mb = speed / (1024 * 1024);
    return `${mb.toFixed(1)} MB/s`;
  };

  const formatTime = (seconds: number) => {
    if (!seconds) return "0s";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const handleDownload = async () => {
    if (!videoInfo) return;

    setDownloading(true);
    setError(null);
    setDownloadProgress({ percent: 0, speed: 0, eta: 0, status: "starting" });

    // Generate a simple client ID
    const clientId = Math.random().toString(36).substring(7);
    
    // Connect to WebSocket
    const ws = new WebSocket(`${WS_BASE}/api/ws/${clientId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.status === "downloading" || data.status === "finished") {
        setDownloadProgress(prev => ({ ...prev, ...data }));
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
    
    try {
      const downloadUrl = `${API_BASE}/api/download?url=${encodeURIComponent(url)}&format_id=${selectedFormat}&client_id=${clientId}`;
      
      const response = await fetch(downloadUrl);
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Download failed");
      }
      
      // Backend returns { status, filename, download_url }
      if (data.status === "success" && data.download_url) {
        setDownloadProgress({ percent: 100, speed: 0, eta: 0, status: "completed" });
        
        // Direct browser to the file URL - this uses Content-Disposition from server
        window.location.href = `${API_BASE}${data.download_url}`;
      } else {
        throw new Error("Download failed - invalid response");
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
      setDownloadProgress(null);
    } finally {
      setDownloading(false);
      ws.close();
      // Keep progress visible for a moment after completion
      if (!error) {
         setTimeout(() => setDownloadProgress(null), 3000);
      }
    }
  };

  const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) {
      return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return "Unknown";
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) {
      return `${(mb / 1024).toFixed(2)} GB`;
    }
    return `${mb.toFixed(2)} MB`;
  };

  const getQualityFormats = () => {
    if (!videoInfo?.formats) return [];
    
    return videoInfo.formats
      .filter((f) => f.resolution && f.resolution !== "audio only")
      .slice(0, 8);
  };

  return (
    <main className="main">
      <div className="hero">
        <div className="logoContainer">
          <div className="logo">
            <svg viewBox="0 0 24 24" fill="currentColor" className="logoIcon">
              <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 3.993L9 16z" />
            </svg>
          </div>
          <h1 className="title">
            <span className="text-gradient">StreamSnag</span>
          </h1>
          <p className="subtitle">
            Download YouTube videos in stunning quality
          </p>
        </div>

        <div className="glass-card inputCard">
          <div className="inputWrapper">
            <input
              type="text"
              className="input-glass"
              placeholder="Paste YouTube URL here..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchVideoInfo()}
            />
            <button
              className="btn-primary fetchBtn"
              onClick={fetchVideoInfo}
              disabled={loading}
            >
              {loading ? (
                <span className="spinner"></span>
              ) : (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="icon">
                    <circle cx="11" cy="11" r="8" />
                    <path d="m21 21-4.35-4.35" />
                  </svg>
                  Fetch
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="error">
              <svg viewBox="0 0 24 24" fill="currentColor" className="errorIcon">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
              </svg>
              {error}
            </div>
          )}
        </div>

        {videoInfo && (
          <div className="glass-card resultCard">
            <div className="videoPreview">
              <div className="thumbnailWrapper">
                <img
                  src={videoInfo.thumbnail}
                  alt={videoInfo.title}
                  className="thumbnail"
                />
                <div className="duration">
                  {formatDuration(videoInfo.duration)}
                </div>
              </div>
              <div className="videoMeta">
                <h2 className="videoTitle">{videoInfo.title}</h2>
                <p className="uploader">{videoInfo.uploader}</p>
              </div>
            </div>

            <div className="formatSection">
              <h3 className="formatTitle">Select Quality</h3>
              <div className="formatGrid">
                <button
                  className={`formatBtn ${selectedFormat === "best" ? "formatBtnActive" : ""}`}
                  onClick={() => setSelectedFormat("best")}
                >
                  <span className="formatLabel">Best</span>
                  <span className="formatDesc">Highest quality</span>
                </button>
                {getQualityFormats().map((format) => (
                  <button
                    key={format.format_id}
                    className={`formatBtn ${selectedFormat === format.format_id ? "formatBtnActive" : ""}`}
                    onClick={() => setSelectedFormat(format.format_id)}
                  >
                    <span className="formatLabel">{format.resolution}</span>
                    <span className="formatDesc">
                      {format.ext.toUpperCase()} • {formatFileSize(format.filesize)}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {downloadProgress ? (
              <div className="progressContainer">
                <div className="progressInfo">
                  <span>{downloadProgress.status === "starting" ? "Starting..." : "Downloading..."}</span>
                  <span>{Math.round(downloadProgress.percent)}%</span>
                </div>
                <div className="progressBar">
                  <div 
                    className="progressFill" 
                    style={{ width: `${downloadProgress.percent}%` }}
                  />
                </div>
                <div className="progressStats">
                  <span>{formatSpeed(downloadProgress.speed)}</span>
                  <span>ETA: {formatTime(downloadProgress.eta)}</span>
                </div>
              </div>
            ) : (
                <button
                  className="btn-primary downloadBtn"
                  onClick={handleDownload}
                  disabled={downloading}
                >
                  {downloading ? (
                    <>
                      <span className="spinner"></span>
                      Downloading...
                    </>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="icon">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7,10 12,15 17,10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      Download Video
                    </>
                  )}
                </button>
            )}
          </div>
        )}
      </div>

      <footer className="footer">
        <p>Built with React & FastAPI</p>
      </footer>
    </main>
  );
}

export default App;
