/**
 * API client — centralized Axios instance for all backend calls.
 *
 * Why a wrapper? So we configure base URL, headers, and error handling
 * in one place instead of repeating it in every component.
 */

import axios from "axios";

const API_BASE_URL =
  process.env.REACT_APP_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// --- Videos ---

export const uploadVideo = async (
  file: File,
  instructorId: string,
  topic?: string
) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("instructor_id", instructorId);
  if (topic) formData.append("topic", topic);

  const response = await api.post("/videos/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const listVideos = async (instructorId?: string) => {
  const params = instructorId ? { instructor_id: instructorId } : {};
  const response = await api.get("/videos", { params });
  return response.data;
};

// --- Evaluations ---

export const createEvaluation = async (
  videoId: string,
  instructorId: string
) => {
  const response = await api.post("/evaluations", {
    video_id: videoId,
    instructor_id: instructorId,
  });
  return response.data;
};

export const getEvaluation = async (evaluationId: string) => {
  const response = await api.get(`/evaluations/${evaluationId}`);
  return response.data;
};

export const getReport = async (evaluationId: string) => {
  const response = await api.get(`/evaluations/${evaluationId}/report`);
  return response.data;
};

export const downloadReportPdf = async (evaluationId: string) => {
  const response = await api.get(`/evaluations/${evaluationId}/report/pdf`, {
    responseType: "blob",
  });
  // Trigger browser download
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = "coaching_report.pdf";
  link.click();
  window.URL.revokeObjectURL(url);
};

export const downloadWorksheetPdf = async (evaluationId: string) => {
  const response = await api.get(`/evaluations/${evaluationId}/worksheet/pdf`, {
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = "reflection_worksheet.pdf";
  link.click();
  window.URL.revokeObjectURL(url);
};

// --- Instructor Dashboard ---

export const getInstructorDashboard = async (instructorId: string) => {
  const response = await api.get(`/instructors/${instructorId}/dashboard`);
  return response.data;
};

export const getMetricTrend = async (
  instructorId: string,
  metricKey: string
) => {
  const response = await api.get(
    `/instructors/${instructorId}/metrics/${metricKey}`
  );
  return response.data;
};

export default api;
