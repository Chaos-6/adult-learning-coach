/**
 * Evaluation Detail / Report View page.
 *
 * Shows the full coaching report for a completed evaluation:
 * 1. Status banner (processing / completed / failed)
 * 2. Metrics overview cards
 * 3. Strengths section (green)
 * 4. Growth areas section (amber)
 * 5. Full markdown report
 * 6. PDF download buttons
 *
 * For in-progress evaluations, shows a polling status view that
 * auto-refreshes every 3 seconds until completion.
 *
 * Route: /evaluations/:evaluationId
 */

import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  LinearProgress,
  Paper,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import AssignmentIcon from "@mui/icons-material/Assignment";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import StarIcon from "@mui/icons-material/Star";
import EmojiObjectsIcon from "@mui/icons-material/EmojiObjects";
import { useQuery } from "@tanstack/react-query";
import {
  getEvaluation,
  getReport,
  downloadReportPdf,
  downloadWorksheetPdf,
} from "../api/client";

/** Status → visual treatment */
const STATUS_CONFIG: Record<
  string,
  { icon: React.ReactElement; color: string; label: string; description: string }
> = {
  queued: {
    icon: <HourglassEmptyIcon />,
    color: "#718096",
    label: "Queued",
    description: "Waiting to start processing...",
  },
  transcribing: {
    icon: <HourglassEmptyIcon />,
    color: "#3182ce",
    label: "Transcribing",
    description: "Converting speech to text with AssemblyAI...",
  },
  analyzing: {
    icon: <HourglassEmptyIcon />,
    color: "#805ad5",
    label: "Analyzing",
    description: "Claude is analyzing your teaching session...",
  },
  completed: {
    icon: <CheckCircleIcon />,
    color: "#38a169",
    label: "Completed",
    description: "Your coaching report is ready!",
  },
  failed: {
    icon: <ErrorIcon />,
    color: "#e53e3e",
    label: "Failed",
    description: "Something went wrong during processing.",
  },
};

/** Simple markdown-to-JSX renderer for the report.
 *
 * We're not pulling in a full markdown library — the report format
 * is predictable (headings, bold, lists, paragraphs), so a lightweight
 * approach avoids an extra dependency.
 */
function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactElement[] = [];
  let key = 0;

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("## ")) {
      elements.push(
        <Typography key={key++} variant="h5" sx={{ mt: 3, mb: 1 }}>
          {trimmed.replace(/^## /, "")}
        </Typography>
      );
    } else if (trimmed.startsWith("### ")) {
      elements.push(
        <Typography key={key++} variant="h6" sx={{ mt: 2, mb: 1 }}>
          {trimmed.replace(/^### /, "")}
        </Typography>
      );
    } else if (trimmed.startsWith("---")) {
      elements.push(<Divider key={key++} sx={{ my: 2 }} />);
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      elements.push(
        <Typography
          key={key++}
          variant="body1"
          sx={{ pl: 2, mb: 0.5 }}
          component="div"
        >
          <span
            dangerouslySetInnerHTML={{
              __html:
                "• " +
                trimmed
                  .replace(/^[-*] /, "")
                  .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>"),
            }}
          />
        </Typography>
      );
    } else if (trimmed.match(/^\d+\.\s/)) {
      elements.push(
        <Typography key={key++} variant="body1" sx={{ pl: 2, mb: 0.5 }} component="div">
          <span
            dangerouslySetInnerHTML={{
              __html: trimmed.replace(
                /\*\*(.+?)\*\*/g,
                "<strong>$1</strong>"
              ),
            }}
          />
        </Typography>
      );
    } else if (trimmed === "") {
      elements.push(<Box key={key++} sx={{ height: 8 }} />);
    } else if (trimmed.startsWith("*") && trimmed.endsWith("*") && !trimmed.startsWith("**")) {
      // Italics line (like footer)
      elements.push(
        <Typography
          key={key++}
          variant="body2"
          color="text.secondary"
          sx={{ fontStyle: "italic", mt: 1 }}
        >
          {trimmed.replace(/^\*|\*$/g, "")}
        </Typography>
      );
    } else {
      elements.push(
        <Typography key={key++} variant="body1" sx={{ mb: 1 }} component="div">
          <span
            dangerouslySetInnerHTML={{
              __html: trimmed.replace(
                /\*\*(.+?)\*\*/g,
                "<strong>$1</strong>"
              ),
            }}
          />
        </Typography>
      );
    }
  }

  return <>{elements}</>;
}

export default function EvaluationDetail() {
  const { evaluationId } = useParams<{ evaluationId: string }>();
  const navigate = useNavigate();

  // Fetch evaluation status (polls while processing)
  const {
    data: evaluation,
    isLoading: evalLoading,
    error: evalError,
  } = useQuery({
    queryKey: ["evaluation", evaluationId],
    queryFn: () => getEvaluation(evaluationId!),
    refetchInterval: (query) => {
      // Poll every 3s while processing, stop when done
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 3000;
    },
    enabled: !!evaluationId,
  });

  // Fetch full report (only when completed)
  const { data: report } = useQuery({
    queryKey: ["report", evaluationId],
    queryFn: () => getReport(evaluationId!),
    enabled: evaluation?.status === "completed",
  });

  if (evalLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (evalError) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        Failed to load evaluation. Check the evaluation ID.
      </Alert>
    );
  }

  if (!evaluation) return null;

  const statusConfig =
    STATUS_CONFIG[evaluation.status] || STATUS_CONFIG.queued;
  const isProcessing = !["completed", "failed"].includes(evaluation.status);

  return (
    <Box>
      {/* Back button */}
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate("/")}
        sx={{ mb: 2 }}
      >
        Back to Dashboard
      </Button>

      {/* Status Banner */}
      <Card
        sx={{
          mb: 3,
          borderLeft: `4px solid ${statusConfig.color}`,
        }}
      >
        <CardContent
          sx={{ display: "flex", alignItems: "center", gap: 2 }}
        >
          <Box sx={{ color: statusConfig.color }}>{statusConfig.icon}</Box>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h6">{statusConfig.label}</Typography>
            <Typography variant="body2" color="text.secondary">
              {statusConfig.description}
            </Typography>
          </Box>
          <Chip
            label={evaluation.status}
            sx={{
              backgroundColor: `${statusConfig.color}20`,
              color: statusConfig.color,
              fontWeight: 600,
            }}
          />
        </CardContent>
        {isProcessing && <LinearProgress />}
      </Card>

      {/* Processing view — show while not completed */}
      {isProcessing && (
        <Card>
          <CardContent sx={{ textAlign: "center", py: 6 }}>
            <CircularProgress size={64} sx={{ mb: 3 }} />
            <Typography variant="h6" gutterBottom>
              Processing your session...
            </Typography>
            <Typography variant="body2" color="text.secondary">
              This typically takes 1-2 minutes. This page will update
              automatically when your report is ready.
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Failed view */}
      {evaluation.status === "failed" && (
        <Alert severity="error">
          The evaluation failed during processing. You can try uploading the
          video again, or check the server logs for details.
        </Alert>
      )}

      {/* Completed view — full report */}
      {evaluation.status === "completed" && report && (
        <>
          {/* PDF Download Buttons */}
          <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
            <Button
              variant="contained"
              startIcon={<PictureAsPdfIcon />}
              onClick={() => downloadReportPdf(evaluationId!)}
            >
              Download Report PDF
            </Button>
            <Button
              variant="outlined"
              startIcon={<AssignmentIcon />}
              onClick={() => downloadWorksheetPdf(evaluationId!)}
            >
              Download Reflection Worksheet
            </Button>
          </Box>

          {/* Metrics Cards */}
          {report.metrics && (
            <>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Session Metrics
              </Typography>
              <Grid container spacing={2} sx={{ mb: 4 }}>
                {[
                  {
                    key: "wpm",
                    label: "Speaking Pace",
                    unit: "WPM",
                    target: "120-160",
                  },
                  {
                    key: "filler_words_per_min",
                    label: "Filler Words",
                    unit: "/min",
                    target: "≤ 3.0",
                  },
                  {
                    key: "questions_per_5min",
                    label: "Questions",
                    unit: "/5 min",
                    target: "≥ 1.0",
                  },
                  {
                    key: "pauses_per_10min",
                    label: "Strategic Pauses",
                    unit: "/10 min",
                    target: "4-6",
                  },
                  {
                    key: "tangent_percentage",
                    label: "Tangent Time",
                    unit: "%",
                    target: "≤ 10%",
                  },
                ]
                  .filter((m) => report.metrics[m.key] != null)
                  .map((m) => (
                    <Grid size={{ xs: 6, sm: 4, md: 2.4 }} key={m.key}>
                      <Card>
                        <CardContent sx={{ textAlign: "center", py: 2 }}>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                          >
                            {m.label}
                          </Typography>
                          <Typography variant="h5" sx={{ my: 0.5 }}>
                            {Number(report.metrics[m.key]).toFixed(1)}
                          </Typography>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                          >
                            {m.unit} (target: {m.target})
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
              </Grid>
            </>
          )}

          {/* Strengths & Growth Areas */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            {report.strengths && report.strengths.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Card sx={{ borderTop: "3px solid #38a169" }}>
                  <CardContent>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        mb: 2,
                      }}
                    >
                      <StarIcon sx={{ color: "success.main" }} />
                      <Typography variant="h6">Strengths</Typography>
                    </Box>
                    {report.strengths.map((s: any, idx: number) => (
                      <Box
                        key={idx}
                        sx={{
                          mb: 2,
                          pb: 2,
                          borderBottom:
                            idx < report.strengths.length - 1
                              ? "1px solid #e2e8f0"
                              : "none",
                        }}
                      >
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          {s.title}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {s.description}
                        </Typography>
                      </Box>
                    ))}
                  </CardContent>
                </Card>
              </Grid>
            )}

            {report.growth_opportunities &&
              report.growth_opportunities.length > 0 && (
                <Grid size={{ xs: 12, md: 6 }}>
                  <Card sx={{ borderTop: "3px solid #d69e2e" }}>
                    <CardContent>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          mb: 2,
                        }}
                      >
                        <EmojiObjectsIcon sx={{ color: "warning.main" }} />
                        <Typography variant="h6">Growth Areas</Typography>
                      </Box>
                      {report.growth_opportunities.map(
                        (g: any, idx: number) => (
                          <Box
                            key={idx}
                            sx={{
                              mb: 2,
                              pb: 2,
                              borderBottom:
                                idx <
                                report.growth_opportunities.length - 1
                                  ? "1px solid #e2e8f0"
                                  : "none",
                            }}
                          >
                            <Typography
                              variant="subtitle2"
                              sx={{ fontWeight: 600 }}
                            >
                              {g.title}
                            </Typography>
                            <Typography
                              variant="body2"
                              color="text.secondary"
                            >
                              {g.description}
                            </Typography>
                          </Box>
                        )
                      )}
                    </CardContent>
                  </Card>
                </Grid>
              )}
          </Grid>

          {/* Full Markdown Report */}
          {report.report_markdown && (
            <Paper sx={{ p: 4 }}>
              <Typography variant="h5" gutterBottom>
                Full Coaching Report
              </Typography>
              <Divider sx={{ mb: 3 }} />
              <SimpleMarkdown text={report.report_markdown} />
            </Paper>
          )}
        </>
      )}
    </Box>
  );
}
