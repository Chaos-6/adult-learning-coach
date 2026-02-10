/**
 * Video Upload page.
 *
 * Provides a drag-and-drop area for uploading training session videos.
 * After upload, the user can kick off an evaluation (transcription + analysis).
 *
 * Flow:
 * 1. User drops/selects a video file
 * 2. We show file info and an optional topic field
 * 3. Upload → POST /api/v1/videos/upload
 * 4. Then optionally start evaluation → POST /api/v1/evaluations
 * 5. Redirect to the evaluation detail page to watch progress
 *
 * Design: The drag-and-drop zone is the primary CTA. We keep the form
 * minimal — just the file and an optional topic. Less friction = more uploads.
 */

import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  LinearProgress,
  TextField,
  Typography,
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import VideoFileIcon from "@mui/icons-material/VideoFile";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { uploadVideo, createEvaluation } from "../api/client";

// MVP: hardcoded instructor ID
const INSTRUCTOR_ID = "3707ea11-ce8a-46dc-a4ae-93a5b895c0bb";

/** Format bytes into human-readable string */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

type UploadStage = "idle" | "uploading" | "uploaded" | "evaluating" | "done";

export default function Upload() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [topic, setTopic] = useState("");
  const [stage, setStage] = useState<UploadStage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFile = useCallback((selectedFile: File) => {
    // Validate file type
    const allowed = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"];
    if (!allowed.includes(selectedFile.type)) {
      setError(
        `Unsupported file type: ${selectedFile.type}. Please upload MP4, MOV, AVI, or WebM.`
      );
      return;
    }

    // Validate file size (10GB max)
    if (selectedFile.size > 10 * 1024 * 1024 * 1024) {
      setError("File too large. Maximum size is 10GB.");
      return;
    }

    setError(null);
    setFile(selectedFile);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) handleFile(droppedFile);
    },
    [handleFile]
  );

  const handleUpload = async () => {
    if (!file) return;

    setError(null);
    setStage("uploading");

    try {
      const result = await uploadVideo(file, INSTRUCTOR_ID, topic || undefined);
      setUploadResult(result);
      setStage("uploaded");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed. Is the backend running?");
      setStage("idle");
    }
  };

  const handleStartEvaluation = async () => {
    if (!uploadResult?.video_id) return;

    setStage("evaluating");
    setError(null);

    try {
      const evaluation = await createEvaluation(
        uploadResult.video_id,
        INSTRUCTOR_ID
      );
      setStage("done");
      // Navigate to evaluation detail page
      setTimeout(() => navigate(`/evaluations/${evaluation.id}`), 1000);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Failed to start evaluation."
      );
      setStage("uploaded");
    }
  };

  return (
    <Box sx={{ maxWidth: 700, mx: "auto" }}>
      <Typography variant="h4" gutterBottom>
        Upload Training Session
      </Typography>
      <Typography variant="subtitle1" sx={{ mb: 4 }}>
        Upload a video of your teaching session for AI-powered coaching
        analysis.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Drop Zone */}
      <Card
        sx={{
          mb: 3,
          border: isDragOver ? "2px dashed #2d8f7b" : "2px dashed #cbd5e0",
          backgroundColor: isDragOver ? "#f0fff4" : "transparent",
          transition: "all 0.2s ease",
          cursor: stage === "idle" ? "pointer" : "default",
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (stage === "idle") setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={stage === "idle" ? handleDrop : undefined}
        onClick={() => {
          if (stage === "idle") {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = "video/mp4,video/quicktime,video/x-msvideo,video/webm";
            input.onchange = (e) => {
              const f = (e.target as HTMLInputElement).files?.[0];
              if (f) handleFile(f);
            };
            input.click();
          }
        }}
      >
        <CardContent
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            py: 6,
          }}
        >
          {!file ? (
            <>
              <CloudUploadIcon
                sx={{ fontSize: 64, color: "text.secondary", mb: 2 }}
              />
              <Typography variant="h6" gutterBottom>
                Drag & drop your video here
              </Typography>
              <Typography variant="body2" color="text.secondary">
                or click to browse — MP4, MOV, AVI, WebM up to 10GB
              </Typography>
            </>
          ) : (
            <>
              <VideoFileIcon
                sx={{ fontSize: 48, color: "primary.main", mb: 1 }}
              />
              <Typography variant="h6">{file.name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {formatFileSize(file.size)}
              </Typography>
              {stage === "idle" && (
                <Button
                  variant="text"
                  size="small"
                  sx={{ mt: 1 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                >
                  Choose a different file
                </Button>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Topic field + Upload button */}
      {file && stage === "idle" && (
        <Box sx={{ mb: 3 }}>
          <TextField
            label="Session Topic (optional)"
            placeholder='e.g., "Introduction to Python" or "Week 3 Lab Review"'
            fullWidth
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            sx={{ mb: 2 }}
          />
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={handleUpload}
            startIcon={<CloudUploadIcon />}
          >
            Upload Video
          </Button>
        </Box>
      )}

      {/* Upload progress */}
      {stage === "uploading" && (
        <Card sx={{ mb: 3 }}>
          <CardContent sx={{ textAlign: "center" }}>
            <CircularProgress sx={{ mb: 2 }} />
            <Typography variant="body1">Uploading {file?.name}...</Typography>
            <LinearProgress sx={{ mt: 2 }} />
          </CardContent>
        </Card>
      )}

      {/* Upload complete — start evaluation */}
      {stage === "uploaded" && (
        <Card sx={{ mb: 3, border: "1px solid #38a169" }}>
          <CardContent sx={{ textAlign: "center" }}>
            <CheckCircleIcon
              sx={{ fontSize: 48, color: "success.main", mb: 1 }}
            />
            <Typography variant="h6" gutterBottom>
              Upload Complete!
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Your video is ready for coaching analysis. This will transcribe
              the audio and generate a detailed coaching report using AI.
            </Typography>
            <Button
              variant="contained"
              color="secondary"
              size="large"
              onClick={handleStartEvaluation}
            >
              Start Coaching Analysis
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Evaluation starting */}
      {stage === "evaluating" && (
        <Card sx={{ mb: 3 }}>
          <CardContent sx={{ textAlign: "center" }}>
            <CircularProgress sx={{ mb: 2 }} />
            <Typography variant="body1">
              Starting analysis pipeline...
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Done — redirecting */}
      {stage === "done" && (
        <Card sx={{ mb: 3, border: "1px solid #38a169" }}>
          <CardContent sx={{ textAlign: "center" }}>
            <CheckCircleIcon
              sx={{ fontSize: 48, color: "success.main", mb: 1 }}
            />
            <Typography variant="h6">
              Analysis started! Redirecting to report...
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
