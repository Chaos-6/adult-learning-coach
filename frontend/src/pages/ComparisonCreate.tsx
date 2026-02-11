/**
 * Comparison creation page — three-step wizard.
 *
 * Step 1: Choose comparison type (Personal Performance / Class Delivery / Program Evaluation)
 * Step 2: Select completed evaluations (2-10)
 * Step 3: Review settings and start analysis
 *
 * The wizard pattern keeps each step focused and prevents information overload.
 * After submission, redirects to the ComparisonDetail page for progress tracking.
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  FormControlLabel,
  LinearProgress,
  Paper,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import AssessmentIcon from "@mui/icons-material/Assessment";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";

import { createComparison, getInstructorDashboard } from "../api/client";

// Hardcoded for MVP — same as Dashboard
const INSTRUCTOR_ID = "3707ea11-ce8a-46dc-a4ae-93a5b895c0bb";

const COMPARISON_TYPES = [
  {
    value: "personal_performance",
    label: "Personal Performance",
    icon: <TrendingUpIcon sx={{ fontSize: 40 }} />,
    description:
      "Track one instructor's growth across multiple sessions. See improvement trends, consistent strengths, and areas still needing work.",
    audience: "Best for: Individual instructor development reviews",
    color: "#2d8f7b",
  },
  {
    value: "class_delivery",
    label: "Class Delivery",
    icon: <CompareArrowsIcon sx={{ fontSize: 40 }} />,
    description:
      "Compare how different instructors deliver the same class. Identify best practices, delivery gaps, and curriculum issues.",
    audience: "Best for: Training managers evaluating a specific course",
    color: "#1a365d",
  },
  {
    value: "program_evaluation",
    label: "Program Evaluation",
    icon: <AssessmentIcon sx={{ fontSize: 40 }} />,
    description:
      "Evaluate overall program quality across a sample of sessions. Assess delivery consistency, content coverage, and systemic patterns.",
    audience: "Best for: Program directors assessing training quality",
    color: "#d69e2e",
  },
];

const STEPS = ["Choose Type", "Select Evaluations", "Review & Start"];

export default function ComparisonCreate() {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [comparisonType, setComparisonType] = useState("");
  const [selectedEvalIds, setSelectedEvalIds] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [classTag, setClassTag] = useState("");
  const [anonymize, setAnonymize] = useState(false);
  const [error, setError] = useState("");

  // Fetch completed evaluations for selection
  const { data: dashboard, isLoading } = useQuery({
    queryKey: ["dashboard", INSTRUCTOR_ID],
    queryFn: () => getInstructorDashboard(INSTRUCTOR_ID),
  });

  const completedEvaluations = (dashboard?.recent_evaluations || []).filter(
    (ev: any) => ev.status === "completed"
  );

  // Create comparison mutation
  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof createComparison>[0]) =>
      createComparison(data),
    onSuccess: (data) => {
      navigate(`/comparisons/${data.id}`);
    },
    onError: (err: any) => {
      setError(
        err?.response?.data?.detail || "Failed to create comparison. Please try again."
      );
    },
  });

  const handleNext = () => {
    if (activeStep === 0 && !comparisonType) {
      setError("Please select a comparison type");
      return;
    }
    if (activeStep === 1 && selectedEvalIds.length < 2) {
      setError("Please select at least 2 evaluations");
      return;
    }
    setError("");
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setError("");
    setActiveStep((prev) => prev - 1);
  };

  const handleToggleEval = (evalId: string) => {
    setSelectedEvalIds((prev) =>
      prev.includes(evalId)
        ? prev.filter((id) => id !== evalId)
        : prev.length < 10
        ? [...prev, evalId]
        : prev
    );
  };

  const handleSubmit = () => {
    if (!title.trim()) {
      setError("Please enter a title for the comparison");
      return;
    }
    createMutation.mutate({
      title: title.trim(),
      comparison_type: comparisonType,
      evaluation_ids: selectedEvalIds,
      created_by_id: INSTRUCTOR_ID,
      class_tag: classTag || undefined,
      anonymize_instructors: anonymize,
      start_immediately: true,
    });
  };

  const selectedType = COMPARISON_TYPES.find((t) => t.value === comparisonType);

  return (
    <Box sx={{ maxWidth: 800, mx: "auto" }}>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        Compare Videos
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Analyze multiple coaching evaluations to identify patterns and trends.
      </Typography>

      {/* Stepper */}
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>
          {error}
        </Alert>
      )}

      {/* Step 1: Choose Type */}
      {activeStep === 0 && (
        <Stack spacing={2}>
          {COMPARISON_TYPES.map((type) => (
            <Card
              key={type.value}
              sx={{
                cursor: "pointer",
                border: comparisonType === type.value
                  ? `2px solid ${type.color}`
                  : "2px solid transparent",
                transition: "all 0.2s",
                "&:hover": {
                  borderColor: type.color,
                  transform: "translateY(-2px)",
                  boxShadow: 3,
                },
              }}
              onClick={() => setComparisonType(type.value)}
            >
              <CardContent sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
                <Box sx={{ color: type.color, mt: 0.5 }}>{type.icon}</Box>
                <Box sx={{ flex: 1 }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {type.label}
                    </Typography>
                    {comparisonType === type.value && (
                      <CheckCircleIcon sx={{ color: type.color, fontSize: 20 }} />
                    )}
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {type.description}
                  </Typography>
                  <Typography variant="caption" sx={{ color: type.color, fontWeight: 600 }}>
                    {type.audience}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      {/* Step 2: Select Evaluations */}
      {activeStep === 1 && (
        <Box>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Select Completed Evaluations
            </Typography>
            <Chip
              label={`${selectedEvalIds.length} / 10 selected`}
              color={selectedEvalIds.length >= 2 ? "success" : "default"}
              size="small"
            />
          </Box>

          {isLoading ? (
            <LinearProgress />
          ) : completedEvaluations.length === 0 ? (
            <Alert severity="info">
              No completed evaluations found. Upload and evaluate videos first.
            </Alert>
          ) : (
            <Stack spacing={1}>
              {completedEvaluations.map((ev: any) => (
                <Paper
                  key={ev.id}
                  sx={{
                    p: 2,
                    cursor: "pointer",
                    border: selectedEvalIds.includes(ev.id)
                      ? "2px solid #2d8f7b"
                      : "2px solid transparent",
                    "&:hover": { backgroundColor: "action.hover" },
                  }}
                  onClick={() => handleToggleEval(ev.id)}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                    <Checkbox
                      checked={selectedEvalIds.includes(ev.id)}
                      onChange={() => handleToggleEval(ev.id)}
                      sx={{ p: 0 }}
                    />
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="subtitle2">
                        {ev.video_filename || "Video evaluation"}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {ev.created_at
                          ? new Date(ev.created_at).toLocaleDateString()
                          : "Date unknown"}{" "}
                        • Status: {ev.status}
                        {ev.metrics?.wpm && ` • WPM: ${ev.metrics.wpm}`}
                      </Typography>
                    </Box>
                    <Chip
                      label={ev.status}
                      size="small"
                      color={ev.status === "completed" ? "success" : "default"}
                    />
                  </Box>
                </Paper>
              ))}
            </Stack>
          )}
        </Box>
      )}

      {/* Step 3: Review & Start */}
      {activeStep === 2 && (
        <Stack spacing={3}>
          <TextField
            label="Comparison Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={
              comparisonType === "personal_performance"
                ? "Q1 Performance Review"
                : comparisonType === "class_delivery"
                ? "Intro to Python — Delivery Comparison"
                : "2025 Training Program Evaluation"
            }
            fullWidth
            required
          />

          {comparisonType === "class_delivery" && (
            <TextField
              label="Class Name / Tag"
              value={classTag}
              onChange={(e) => setClassTag(e.target.value)}
              placeholder="e.g., Intro to Python, Leadership 101"
              fullWidth
              helperText="Used to label this comparison as a specific class"
            />
          )}

          <FormControlLabel
            control={
              <Switch
                checked={anonymize}
                onChange={(e) => setAnonymize(e.target.checked)}
              />
            }
            label="Anonymize instructor names in the report"
          />

          <Paper sx={{ p: 2, backgroundColor: "grey.50" }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Summary
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Type:</strong> {selectedType?.label}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Evaluations:</strong> {selectedEvalIds.length} selected
            </Typography>
            {classTag && (
              <Typography variant="body2" color="text.secondary">
                <strong>Class:</strong> {classTag}
              </Typography>
            )}
            <Typography variant="body2" color="text.secondary">
              <strong>Anonymized:</strong> {anonymize ? "Yes" : "No"}
            </Typography>
          </Paper>

          {createMutation.isPending && <LinearProgress />}
        </Stack>
      )}

      {/* Navigation buttons */}
      <Box sx={{ display: "flex", justifyContent: "space-between", mt: 4 }}>
        <Button
          disabled={activeStep === 0}
          onClick={handleBack}
          variant="outlined"
        >
          Back
        </Button>
        {activeStep < STEPS.length - 1 ? (
          <Button onClick={handleNext} variant="contained">
            Next
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={createMutation.isPending}
            color="primary"
          >
            {createMutation.isPending ? "Creating..." : "Start Comparison"}
          </Button>
        )}
      </Box>
    </Box>
  );
}
