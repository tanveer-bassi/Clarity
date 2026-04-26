# Clarity: Vision-First Autonomous Document Intelligence

Clarity is an enterprise-grade AI platform engineered to perform deep relational analysis of legal, medical, and commercial agreements. By leveraging a multi-stage hybrid intelligence pipeline, Clarity identifies latent asymmetric risks and translates complex contractual obligations into actionable executive summaries.

---

## Technical Overview

Clarity addresses the systemic issue of contractual opacity. While traditional OCR systems focus on character recognition, Clarity recognizes intent. The platform identifies the direct relationship between clauses, surfaces high-probability liability hooks, and scores document risk based on industry-standard security and medical benchmarks.

## Core Architecture

The platform is designed with a modular, decoupled architecture distributed across three primary layers:

### 1. Presentation Layer (Frontend)
- **Engine**: Developed in Vanilla HTML5 and ES6+ JavaScript to ensure maximum performance and minimal latency.
- **Design System**: A high-fidelity, grid-based UI utilizing the **Instrument Serif** and **Manrope** typography systems. 
- **Animation Framework**: Native `IntersectionObserver` implementations provide an editorial-grade scroll experience without the overhead of external libraries.

### 2. Analysis Engine (Backend)
Orchestrated via a high-performance **FastAPI** environment, the pipeline follows a rigorous processing order:
- **Vision-First OCR (Google Cloud Vision API)**: Captures document geometry and spatial relationships, ensuring that context is preserved beyond simple raw text.
- **Distributed Processing (DCP)**: Leverages the Distributive Compute Protocol (DCP) to parallelize page analysis across a network of compute nodes, significantly reducing total turnaround time for high-volume documents.
- **Custom Transformer Models (DistilBERT)**: A specialized multi-label classifier fine-tuned on curated legal datasets, providing deterministic risk categorization across key vectors (Arbitration, Indemnity, Liability).
- **Generative Synthesis (Google Gemma/Gemini)**: Performs high-accuracy translation of "legalese" into deterministic summaries, maintaining strict adherence to the source text.

### 3. Persistence & Vaulting
- **Backboard Integration**: Utilizes a secure, trusted consent vault to manage the persistent lifecycle of analyzed documents and user agreements.

---

## Risk Categorization Vectors

Clarity’s custom DistilBERT model is trained to identify and categorize risks in nine critical domains, including:
- **Financial Exposure**: Identification of uncapped liability and aggressive indemnity structures.
- **Rights Waiver**: Detection of mandatory arbitration and jury trial waivers.
- **Operational Persistence**: Monitoring for auto-renewal hooks and termination-for-convenience triggers.
- **Legal Jurisdiction**: Surface-level mapping of governing laws and venue restrictions.

---

## Implementation and Deployment

### Frontend Environment
```bash
cd frontend
npm install
npm run dev
```

### Backend Environment
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## Design Philosophy
- **Precision Typography**: Optimized for high readability in high-stakes environments.
- **Zero-Latency Feel**: Utilization of HMR (Hot Module Replacement) and optimized asset pipelines for instantaneous user feedback.
- **Technical Transparency**: The "Decision Brief" interface provides a one-to-one mapping between AI-generated flags and documented source material.

---

*Coded for Hackathon 2026 Submission. Focus: Autonomous Intelligence and Privacy-Preserving Security.*
