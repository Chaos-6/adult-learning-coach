/**
 * Comparison Detail / Report View page.
 *
 * Mirrors EvaluationDetail but for comparisons:
 * 1. Status banner with polling while analyzing
 * 2. Linked evaluations list
 * 3. Comparison metrics overview
 * 4. Strengths & growth areas
 * 5. Full comparison report (markdown)
 * 6. PDF download button
 *
 * Note: dangerouslySetInnerHTML is used for markdown rendering of
 * server-generated content (from our own Claude analysis pipeline).
 * This content is NOT user-supplied — it comes from our backend's
 * analysis service. Same pattern as EvaluationDetail.tsx.
 *
 * Route: /comparisons/:comparisonId
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
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import StarIcon from "@mui/icons-material/Star";
import EmojiObjectsIcon from "@mui/icons-material/EmojiObjects";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import { useQuery } from "@tanstack/react-query";
import {
  getComparison,
  getComparisonReport,
  downloadComparisonReportPdf,
} from "../api/client";

const STATUS_CONFIG: Record<
  string,
  { icon: React.ReactElement; color: string; label: string; description: string }
> = {
  draft: {
    icon: <HourglassEmptyIcon />,
    color: "#718096",
    label: "Draft",
    description: "Comparison configured but not yet started.",
  },
  queued: {
    icon: <HourglassEmptyIcon />,
    color: "#718096",
    label: "Queued",
    description: "Waiting to start analysis...",
  },
  analyzing: {
    icon: <HourglassEmptyIcon />,
    color: "#805ad5",
    label: "Analyzing",
    description: "Claude is comparing your evaluations...",
  },
  completed: {
    icon: <CheckCircleIcon />,
    color: "#38a169",
    label: "Completed",
    description: "Your comparison report is ready!",
  },
  failed: {
    icon: <ErrorIcon />,
    color: "#e53e3e",
    label: "Failed",
    description: "Something went wrong during comparison analysis.",
  },
};

const TYPE_LABELS: Record<string, string> = {
  personal_performance: "Personal Performance",
  class_delivery: "Class Delivery",
  program_evaluation: "Program Evaluation",
};

/**
 * Simple markdown-to-JSX renderer (same pattern as EvaluationDetail).
 *
 * Content comes from our backend analysis pipeline (Claude-generated),
 * not from arbitrary user input, so innerHTML usage is acceptable here.
 * Same approach used in the existing EvaluationDetail page.
 */
function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactElement[] = [];
  let key = 0;

  const boldify = (s: string) =>
    s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("# ") && !trimmed.startsWith("## ")) {
      elements.push(
        <Typography key={key++} variant="h4" sx={{ mt: 3, mb: 2, fontWeight: 700 }}>
          {trimmed.replace(/^# /, "")}
        </Typography>
      );
    } else if (trimmed.startsWith("## ")) {
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
      const content = "• " + boldify(trimmed.replace(/^[-*] /, ""));
      elements.push(
        <Typography key={key++} variant="body1" sx={{ pl: 2, mb: 0.5 }} component="div">
          {/* Server-generated content from our analysis pipeline */}
          <span dangerouslySetInnerHTML={{ __html: content }} />
        </Typography>
      );
    } else if (trimmed.match(/^\d+\.\s/)) {
      elements.push(
        <Typography key={key++} variant="body1" sx={{ pl: 2, mb: 0.5 }} component="div">
          <span dangerouslySetInnerHTML={{ __html: boldify(trimmed) }} />
        </Typography>
      );
    } else if (trimmed.startsWith("|")) {
      elements.push(
        <Typography
          key={key++}
          variant="body2"
          sx={{ fontFamily: "monospace", fontSize: "0.85rem", mb: 0.25 }}
        >
          {trimmed}
        </Typography>
      );
    } else if (trimmed === "") {
      elements.push(<Box key={key++} sx={{ height: 8 }} />);
    } else if (trimmed.startsWith("*") && trimmed.endsWith("*") && !trimmed.startsWith("**")) {
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
          <span dangerouslySetInnerHTML={{ __html: boldify(trimmed) }} />
        </Typography>
      );
    }
  }

  return <>{elements}</>;
}

export default function ComparisonDetail() {
  const { comparisonId } = useParams<{ comparisonId: string }>();
  const navigate = useNavigate();

  // Fetch comparison status (polls while processing)
  const {
    data: comparison,
    isLoading,
    error: loadError,
  } = useQuery({
    queryKey: ["comparison", comparisonId],
    queryFn: () => getComparison(comparisonId!),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 3000;
    },
    enabled: !!comparisonId,
  });

  // Fetch full report (only when completed)
  const { data: report } = useQuery({
    queryKey: ["comparisonReport", comparisonId],
    queryFn: () => getComparisonReport(comparisonId!),
    enabled: comparison?.status === "completed",
  });

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (loadError) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        Failed to load comparison. Check the comparison ID.
      </Alert>
    );
  }

  if (!comparison) return null;

  const statusConfig = STATUS_CONFIG[comparison.status] || STATUS_CONFIG.queued;
  const isProcessing = !["completed", "failed", "draft"].includes(comparison.status);

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

      {/* Title + Type */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
        <CompareArrowsIcon sx={{ fontSize: 32, color: "primary.main" }} />
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {comparison.title}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {TYPE_LABELS[comparison.comparison_type] || comparison.comparison_type}
            {" • "}
            {comparison.evaluations?.length || 0} evaluations compared
          </Typography>
        </Box>
      </Box>

      {/* Status Banner */}
      <Card sx={{ mb: 3, borderLeft: `4px solid ${statusConfig.color}` }}>
        <CardContent sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Box sx={{ color: statusConfig.color }}>{statusConfig.icon}</Box>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h6">{statusConfig.label}</Typography>
            <Typography variant="body2" color="text.secondary">
              {statusConfig.description}
            </Typography>
          </Box>
          <Chip
            label={comparison.status}
            sx={{
              backgroundColor: `${statusConfig.color}20`,
              color: statusConfig.color,
              fontWeight: 600,
            }}
          />
        </CardContent>
        {isProcessing && <LinearProgress />}
      </Card>

      {/* Linked Evaluations */}
      {comparison.evaluations && comparison.evaluations.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Included Evaluations
            </Typography>
            {comparison.evaluations.map((ev: any, idx: number) => (
              <Box
                key={ev.evaluation_id}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 2,
                  py: 1,
                  borderBottom:
                    idx < comparison.evaluations.length - 1
                      ? "1px solid #e2e8f0"
                      : "none",
                }}
              >
                <Chip
                  label={ev.label || `Session ${ev.display_order + 1}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
                <Typography variant="body2" sx={{ flex: 1 }}>
                  {ev.instructor_name || "Unknown instructor"}
                </Typography>
                <Chip
                  label={ev.status || "unknown"}
                  size="small"
                  color={ev.status === "completed" ? "success" : "default"}
                />
                <Button
                  size="small"
                  onClick={() => navigate(`/evaluations/${ev.evaluation_id}`)}
                >
                  View
                </Button>
              </Box>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Processing view */}
      {isProcessing && (
        <Card>
          <CardContent sx={{ textAlign: "center", py: 6 }}>
            <CircularProgress size={64} sx={{ mb: 3 }} />
            <Typography variant="h6" gutterBottom>
              Analyzing your evaluations...
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Claude is comparing {comparison.evaluations?.length || 0} evaluation
              reports. This typically takes 1-3 minutes. This page will update
              automatically.
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Failed view */}
      {comparison.status === "failed" && (
        <Alert severity="error">
          The comparison analysis failed. Check the server logs for details.
          {comparison.metrics?.error && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              Error: {comparison.metrics.error}
            </Typography>
          )}
        </Alert>
      )}

      {/* Completed view — full report */}
      {comparison.status === "completed" && report && (
        <>
          {/* PDF Download */}
          <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
            <Button
              variant="contained"
              startIcon={<PictureAsPdfIcon />}
              onClick={() => downloadComparisonReportPdf(comparisonId!)}
            >
              Download Comparison Report PDF
            </Button>
          </Box>

          {/* Strengths & Growth Areas */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            {report.strengths && report.strengths.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Card sx={{ borderTop: "3px solid #38a169" }}>
                  <CardContent>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
                      <StarIcon sx={{ color: "success.main" }} />
                      <Typography variant="h6">Cross-Session Strengths</Typography>
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
                          {s.text || s.description}
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
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
                        <EmojiObjectsIcon sx={{ color: "warning.main" }} />
                        <Typography variant="h6">Growth Opportunities</Typography>
                      </Box>
                      {report.growth_opportunities.map((g: any, idx: number) => (
                        <Box
                          key={idx}
                          sx={{
                            mb: 2,
                            pb: 2,
                            borderBottom:
                              idx < report.growth_opportunities.length - 1
                                ? "1px solid #e2e8f0"
                                : "none",
                          }}
                        >
                          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                            {g.title}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {g.text || g.description}
                          </Typography>
                        </Box>
                      ))}
                    </CardContent>
                  </Card>
                </Grid>
              )}
          </Grid>

          {/* Full Markdown Report */}
          {report.report_markdown && (
            <Paper sx={{ p: 4 }}>
              <Typography variant="h5" gutterBottom>
                Full Comparison Report
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
