# Adult Learning Coaching Agent (ALCA)

**AI-powered instructional coaching for distance learning evaluation.**

ALCA transforms video recordings of training sessions into comprehensive, evidence-based coaching reports. Upload a teaching video, and the system automatically transcribes the audio, analyzes teaching effectiveness across four research-backed dimensions, and generates a professional PDF coaching report with actionable feedback.

Built for corporate training departments, EdTech companies, professional development providers, and anyone responsible for improving instructor quality at scale.

---

## What It Does

| Without ALCA | With ALCA |
|---|---|
| 10-14 hours per evaluation (watch video, take notes, write report) | 90-120 minutes (upload, automated analysis, coach review) |
| Subjective feedback varies by evaluator | Standardized rubric applied consistently every time |
| No historical tracking | Longitudinal trends across 10+ sessions |
| Feedback weeks after the session | Report ready in minutes |

### The Pipeline

```
Video Upload  -->  Transcription  -->  AI Analysis  -->  PDF Report
  (MP4/MOV)      (AssemblyAI)       (Claude)         (ReportLab)
                  Speaker labels     4 dimensions      Branded report
                  Timestamps         Metrics + evidence Reflection worksheet
```

### Analysis Framework (4 Dimensions)

1. **Clarity & Pacing** - Speaking pace (target 120-160 WPM), strategic pauses, filler word frequency, jargon detection
2. **Engagement Techniques** - Question frequency and types, vocal variety, participation invitations
3. **Explanation Quality** - Analogy effectiveness, example relevance to adult learners, scaffolding from foundational to advanced
4. **Time Management** - Tangent detection (<10% of class time), pacing balance, structural signposting

Every observation is backed by a timestamped citation from the transcript. Metrics include shown calculations so instructors understand exactly how scores are derived.

---

## Key Features

### For Instructors
- Upload training session videos (MP4, MOV, WebM, AVI up to 10GB)
- View AI-generated coaching reports with strengths and growth areas
- Download professional PDF reports and reflection worksheets
- Track improvement over time with trend charts

### For Coaches & Administrators
- Review AI-generated reports before sharing with instructors
- Compare instructor performance across sessions
- Identify organization-wide patterns (recurring strengths and gaps)
- Dashboard with aggregated metrics and evaluation history

### Report Output
- **Coaching Report** (12-20 pages): Executive summary, strengths, growth opportunities, prioritized improvements, timestamped teaching moments, metrics snapshot, next steps
- **Reflection Worksheet** (3 pages): Guided self-reflection prompts with writing space for instructors to plan their own development

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python, FastAPI | Async-first, automatic OpenAPI docs, dependency injection |
| **Database** | PostgreSQL + JSONB | Relational integrity for users/videos + flexible schema for metrics |
| **Transcription** | AssemblyAI | Speaker diarization, timestamps, high accuracy on technical content |
| **AI Analysis** | Claude (Anthropic) | 200K context window handles 6-hour transcripts, low temperature (0.3) for reproducibility |
| **PDF Generation** | ReportLab | On-demand rendering (<100ms), no storage needed, professional typography |
| **Frontend** | React 18 + TypeScript | MUI components, React Query for data fetching, React Router |
| **Tests** | pytest + httpx | 26 async integration tests against real PostgreSQL |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- [AssemblyAI API key](https://www.assemblyai.com/)
- [Anthropic API key](https://console.anthropic.com/)

### Setup

**1. Clone and configure:**
```bash
git clone https://github.com/Chaos-6/adult-learning-coach.git
cd adult-learning-coach
```

**2. Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env from the template
cp .env.example .env
# Edit .env with your database URL, API keys, and secret key

# Start the server
uvicorn app.main:app --reload --port 8000
```

**3. Frontend:**
```bash
cd frontend
npm install
npm start
```

The app opens at **http://localhost:3000**. The backend API is at **http://localhost:8000**.

**4. Run tests:**
```bash
cd backend
python -m pytest
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/videos/upload` | Upload a training video |
| `GET` | `/api/v1/videos` | List videos (paginated) |
| `GET` | `/api/v1/videos/{id}` | Get video details |
| `DELETE` | `/api/v1/videos/{id}` | Delete a video |
| `POST` | `/api/v1/evaluations` | Start a coaching evaluation |
| `GET` | `/api/v1/evaluations/{id}` | Check evaluation status |
| `GET` | `/api/v1/evaluations/{id}/transcript` | Get transcript text |
| `GET` | `/api/v1/evaluations/{id}/report` | Get coaching report (JSON) |
| `GET` | `/api/v1/evaluations/{id}/report/pdf` | Download coaching report PDF |
| `GET` | `/api/v1/evaluations/{id}/worksheet/pdf` | Download reflection worksheet PDF |
| `GET` | `/api/v1/instructors/{id}/dashboard` | Instructor performance dashboard |
| `GET` | `/api/v1/instructors/{id}/evaluations` | Evaluation history (paginated) |
| `GET` | `/api/v1/instructors/{id}/metrics/{key}` | Single metric trend data |
| `GET` | `/health` | Health check with database status |

Interactive API documentation available at **http://localhost:8000/docs** when the server is running.

---

## Project Structure

```
adult-learning-coach/
  backend/
    app/
      models/         # SQLAlchemy models (User, Video, Transcript, Evaluation)
      routers/        # FastAPI route handlers (videos, evaluations, instructors)
      schemas/        # Pydantic request/response schemas
      services/       # Business logic
        analysis.py       # Claude coaching analysis
        prompts.py        # Coaching prompt engineering
        transcription.py  # AssemblyAI integration
        evaluation.py     # Pipeline orchestrator
        pdf_report.py     # PDF generation
        storage.py        # File storage abstraction
      config.py       # Environment configuration
      database.py     # Async SQLAlchemy setup
      main.py         # FastAPI app entry point
    tests/            # 26 integration tests
  frontend/
    src/
      api/            # Axios API client
      components/     # Layout, navigation
      pages/          # Dashboard, Upload, EvaluationDetail
      theme/          # MUI theme configuration
```

---

## Development Status

This is an MVP (Phase 1) implementation covering the core coaching pipeline. See the [Production PRD](docs/) for the full product vision.

### What's Built (MVP)
- Video upload with format validation
- AssemblyAI transcription with speaker diarization
- Claude-powered coaching analysis (all 4 dimensions)
- PDF report and reflection worksheet generation
- Historical performance tracking with trend detection
- React dashboard with metric charts and evaluation history
- 26 backend integration tests

### What's Next (Phase 2)
- Authentication and role-based access control
- AWS S3 storage (currently local filesystem)
- Celery task queue for production-scale processing
- Coach and administrator views
- Video hosting with timestamped playback
- Collaborative coaching (multi-reviewer)
- Custom coaching rubrics per organization
- Mobile application

---

## Cost Per Evaluation

| Component | 1-hour video | 6-hour video |
|-----------|-------------|-------------|
| AssemblyAI transcription | $0.90 | $5.40 |
| Claude analysis | ~$0.38 | ~$0.38 |
| PDF generation | <$0.01 | <$0.01 |
| **Total** | **~$1.30** | **~$5.85** |

---

## License

Private repository. All rights reserved.
