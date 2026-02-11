/**
 * Instructor Dashboard page.
 *
 * This is the "home page" for an instructor. It shows:
 * 1. Summary stats (total evaluations, sessions analyzed)
 * 2. Metric trend cards (speaking pace, filler words, etc.)
 * 3. Top strengths and recurring growth areas
 * 4. Recent evaluations list with links to reports
 * 5. Recent comparisons list with links to comparison reports
 *
 * Data comes from:
 *   - GET /api/v1/instructors/{id}/dashboard (evaluations)
 *   - GET /api/v1/comparisons (comparisons)
 *
 * Design decision: We hardcode the instructor ID for now (MVP).
 * In a real app, this would come from authentication context.
 */

import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import TrendingFlatIcon from "@mui/icons-material/TrendingFlat";
import StarIcon from "@mui/icons-material/Star";
import EmojiObjectsIcon from "@mui/icons-material/EmojiObjects";
import AssessmentIcon from "@mui/icons-material/Assessment";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import { useQuery } from "@tanstack/react-query";
import { getInstructorDashboard, listComparisons } from "../api/client";

// MVP: hardcoded instructor ID from our seed data
const INSTRUCTOR_ID = "3707ea11-ce8a-46dc-a4ae-93a5b895c0bb";

/** Trend direction → icon + color */
function TrendIndicator({ direction }: { direction: string | null }) {
  if (!direction) return <Chip label="New" size="small" variant="outlined" />;

  const config: Record<string, { icon: React.ReactElement; color: string; label: string }> = {
    improving: {
      icon: <TrendingUpIcon fontSize="small" />,
      color: "#38a169",
      label: "Improving",
    },
    declining: {
      icon: <TrendingDownIcon fontSize="small" />,
      color: "#e53e3e",
      label: "Declining",
    },
    stable: {
      icon: <TrendingFlatIcon fontSize="small" />,
      color: "#718096",
      label: "Stable",
    },
  };

  const c = config[direction] || config.stable;

  return (
    <Chip
      icon={c.icon}
      label={c.label}
      size="small"
      sx={{
        backgroundColor: `${c.color}15`,
        color: c.color,
        fontWeight: 600,
        "& .MuiChip-icon": { color: c.color },
      }}
    />
  );
}

/** Format a metric value with its unit */
function formatMetric(value: number | null | undefined, unit: string): string {
  if (value == null) return "—";
  return `${value.toFixed(1)} ${unit}`;
}

export default function Dashboard() {
  const navigate = useNavigate();

  const {
    data: dashboard,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["dashboard", INSTRUCTOR_ID],
    queryFn: () => getInstructorDashboard(INSTRUCTOR_ID),
  });

  // Fetch recent comparisons (independent of the dashboard query)
  const { data: comparisonsData } = useQuery({
    queryKey: ["comparisons", "recent"],
    queryFn: () => listComparisons({ page: 1, page_size: 5 }),
  });

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        Failed to load dashboard. Is the backend running on localhost:8000?
      </Alert>
    );
  }

  if (!dashboard) return null;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Welcome back, {dashboard.instructor_name}
        </Typography>
        <Typography variant="subtitle1">
          {dashboard.total_sessions_analyzed} sessions analyzed across{" "}
          {dashboard.total_evaluations} evaluations
        </Typography>
      </Box>

      {/* Metric Trend Cards */}
      <Typography variant="h6" sx={{ mb: 2 }}>
        Performance Metrics
      </Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        {dashboard.metric_trends?.map((metric: any) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={metric.metric_name}>
            <Card>
              <CardContent>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    mb: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    {metric.display_name}
                  </Typography>
                  <TrendIndicator direction={metric.trend_direction} />
                </Box>

                <Typography variant="h4" sx={{ mb: 0.5 }}>
                  {formatMetric(metric.current_value, metric.unit)}
                </Typography>

                <Box sx={{ display: "flex", gap: 2, mt: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    Avg: {formatMetric(metric.average_value, metric.unit)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Best: {formatMetric(metric.best_value, metric.unit)}
                  </Typography>
                </Box>

                {/* Target range indicator */}
                {(metric.target_min != null || metric.target_max != null) && (
                  <Typography
                    variant="caption"
                    sx={{ color: "text.secondary", display: "block", mt: 0.5 }}
                  >
                    Target:{" "}
                    {metric.target_min != null && metric.target_max != null
                      ? `${metric.target_min}–${metric.target_max} ${metric.unit}`
                      : metric.target_max != null
                      ? `≤ ${metric.target_max} ${metric.unit}`
                      : `≥ ${metric.target_min} ${metric.unit}`}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Strengths & Growth Areas */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
                <StarIcon sx={{ color: "success.main" }} />
                <Typography variant="h6">Top Strengths</Typography>
              </Box>
              {dashboard.top_strengths?.length > 0 ? (
                dashboard.top_strengths.map((item: any, idx: number) => (
                  <Box
                    key={idx}
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      py: 1,
                      borderBottom:
                        idx < dashboard.top_strengths.length - 1
                          ? "1px solid #e2e8f0"
                          : "none",
                    }}
                  >
                    <Typography variant="body2">{item.title}</Typography>
                    <Chip
                      label={`${item.count}/${item.total_evaluations} sessions`}
                      size="small"
                      color="success"
                      variant="outlined"
                    />
                  </Box>
                ))
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Complete more evaluations to see recurring strengths.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
                <EmojiObjectsIcon sx={{ color: "warning.main" }} />
                <Typography variant="h6">Growth Areas</Typography>
              </Box>
              {dashboard.recurring_growth_areas?.length > 0 ? (
                dashboard.recurring_growth_areas.map((item: any, idx: number) => (
                  <Box
                    key={idx}
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      py: 1,
                      borderBottom:
                        idx < dashboard.recurring_growth_areas.length - 1
                          ? "1px solid #e2e8f0"
                          : "none",
                    }}
                  >
                    <Typography variant="body2">{item.title}</Typography>
                    <Chip
                      label={`${item.count}/${item.total_evaluations} sessions`}
                      size="small"
                      color="warning"
                      variant="outlined"
                    />
                  </Box>
                ))
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Complete more evaluations to see recurring growth areas.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Evaluations Table */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
        <AssessmentIcon sx={{ color: "primary.main" }} />
        <Typography variant="h6">Recent Evaluations</Typography>
      </Box>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Video</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="center">Strengths</TableCell>
              <TableCell align="center">Growth Areas</TableCell>
              <TableCell>WPM</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {dashboard.evaluations?.length > 0 ? (
              dashboard.evaluations.map((eval_: any) => (
                <TableRow
                  key={eval_.id}
                  hover
                  sx={{ cursor: "pointer" }}
                  onClick={() => navigate(`/evaluations/${eval_.id}`)}
                >
                  <TableCell>
                    {eval_.video_filename || "Untitled video"}
                  </TableCell>
                  <TableCell>
                    {new Date(eval_.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={eval_.status}
                      size="small"
                      color={
                        eval_.status === "completed"
                          ? "success"
                          : eval_.status === "failed"
                          ? "error"
                          : "default"
                      }
                    />
                  </TableCell>
                  <TableCell align="center">{eval_.strength_count}</TableCell>
                  <TableCell align="center">{eval_.growth_area_count}</TableCell>
                  <TableCell>
                    {eval_.metrics?.wpm
                      ? `${eval_.metrics.wpm.toFixed(0)} WPM`
                      : "—"}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                    No evaluations yet. Upload a video to get started!
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Recent Comparisons */}
      {comparisonsData && comparisonsData.items?.length > 0 && (
        <Box sx={{ mt: 4 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
            <CompareArrowsIcon sx={{ color: "primary.main" }} />
            <Typography variant="h6">Recent Comparisons</Typography>
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Title</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Evaluations</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Date</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {comparisonsData.items.map((comp: any) => (
                  <TableRow
                    key={comp.id}
                    hover
                    sx={{ cursor: "pointer" }}
                    onClick={() => navigate(`/comparisons/${comp.id}`)}
                  >
                    <TableCell>{comp.title}</TableCell>
                    <TableCell>
                      <Chip
                        label={
                          comp.comparison_type === "personal_performance"
                            ? "Personal"
                            : comp.comparison_type === "class_delivery"
                            ? "Class"
                            : "Program"
                        }
                        size="small"
                        variant="outlined"
                        color="primary"
                      />
                    </TableCell>
                    <TableCell>{comp.evaluations?.length || 0}</TableCell>
                    <TableCell>
                      <Chip
                        label={comp.status}
                        size="small"
                        color={
                          comp.status === "completed"
                            ? "success"
                            : comp.status === "failed"
                            ? "error"
                            : comp.status === "analyzing"
                            ? "warning"
                            : "default"
                        }
                      />
                    </TableCell>
                    <TableCell>
                      {new Date(comp.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Box>
  );
}
