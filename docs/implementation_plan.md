# Privacy Exposure Tool Revamp Plan

This document outlines the proposed architectural revamp and new features for the Privacy Exposure Tool. The goal is to evolve the project from a standalone desktop script into a scalable, multi-user, web-accessible platform.

## User Review Required
> [!IMPORTANT]
> Please review the proposed architecture and feature additions below. Let me know which features you want to prioritize first (e.g., should we start with building the FastAPI backend, or do you want to keep it as a desktop app but just add a database?).

## Open Questions
> [!WARNING]
> 1. **Frontend Preference**: Do you want to keep the PyQt5 Desktop App, or should we replace it with a modern, responsive Web Application (e.g., using React/Vite) that connects to the FastAPI backend?
> 2. **Database**: Is SQLite sufficient for local testing, or do you want to set up PostgreSQL?
> 3. **PII Detection**: Do you want to upgrade the detection engine to use NLP (like Microsoft Presidio or spaCy) to detect Names, Addresses, and Credit Cards, rather than just relying on Regex for emails/phones?

---

## 🚀 Proposed Improvements & Features

### 1. Architectural Revamp (FastAPI Backend)
Currently, the UI and the processing logic are tightly coupled. We will decouple them:
- **FastAPI Backend**: Move all heavy lifting (OCR, Image Blurring, Regex, PDF Generation) to API endpoints (e.g., `POST /scan`, `POST /blur`, `GET /report`).
- **Benefits**: This allows the tool to be used as a service. You can have a Web App, a Desktop App, or even a Mobile App communicate with the same backend. It also prevents the UI from freezing during heavy OCR tasks.

### 2. Database Integration
Add a database (SQLite/PostgreSQL) using an ORM like SQLAlchemy to persist data.
- **Users Table**: Store user credentials and manage authentication.
- **Scans Table**: Keep a history of past scans, storing the original filename, upload date, privacy score, and risk level.
- **Findings Table**: Store the extracted emails, phones, and passwords linked to a specific scan so users can review past reports without re-uploading the image.

### 3. User Authentication & Multi-Tenancy
- Implement JWT (JSON Web Token) authentication.
- Users will have their own accounts and personal dashboards.
- Users can only see their own scan history and generated reports.

### 4. Enhanced Detection Engine (NLP)
- Regex is good for structured data (emails, phones), but struggles with unstructured data like Names, Physical Addresses, and Organization names.
- We can integrate **Microsoft Presidio** or **spaCy** to detect a wider range of PII entities with higher accuracy.

### 5. Asynchronous Processing & Background Tasks
- OCR and image blurring can be slow for large PDFs or high-res images.
- Implement background tasks (using FastAPI's `BackgroundTasks` or Celery) so the user gets an immediate response ("Scan in progress...") and can view the results when ready.

---

## 🛠️ Implementation Phases

### Phase 1: Core Backend Migration
- Set up FastAPI project structure.
- Create endpoints for `/upload`, `/analyze`, and `/blur`.
- Migrate `detect_sensitive.py`, `smart_blur.py`, and `privacy_score.py` into FastAPI service controllers.

### Phase 2: Database & Auth
- Set up SQLAlchemy with SQLite.
- Create Models (`User`, `ScanRecord`).
- Implement JWT Login/Signup endpoints.

### Phase 3: Frontend Update
- (Option A) Update PyQt5 to make HTTP requests to the FastAPI backend.
- (Option B) Build a new modern Web App with React/Vite that provides a stunning dashboard for users to log in, upload files, and view their scan history.

## Verification Plan
### Automated Tests
- Write pytest cases for FastAPI endpoints to ensure OCR and Blurring logic works via HTTP.
### Manual Verification
- Start the API server, upload test images via Swagger UI or Frontend, and verify the database records and blurred outputs.
