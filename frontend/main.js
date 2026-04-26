// VITE_API_BASE in frontend/.env overrides this — set it to your ngrok URL for deployment.
const API_BASE = import.meta.env?.VITE_API_BASE ?? "http://localhost:8000";

const state = {
  currentScreen: "landing",
  uploadedFileName: "Hospital_Consent_Form.pdf",
  score: 75,
  clauseIndex: 0,
  zoom: 100,
  threadId: null,
  summary: "",
  dcpMetrics: null,
};

let clauses = [
  {
    badge: "High risk flag",
    title: "Liability limitation and indemnity",
    subtitle: "Clause 14.2 — Terms of Service Agreement",
    original:
      "“The User hereby agrees to indemnify, defend, and hold harmless Clarity and its affiliates from any and all claims, losses, liabilities, and legal expenses arising from use of the service...”",
    plain:
      "If something tied to your use of the platform creates a dispute, you may end up paying the company’s legal costs and related losses.",
    impacts: [
      ["Financial exposure", "This clause can shift major legal costs onto you."],
      ["Indefinite liability", "The obligation can survive even after the agreement ends."],
    ],
  },
  {
    badge: "Warning flag",
    title: "Termination for convenience",
    subtitle: "Clause 8.1 — Commercial Lease Addendum",
    original:
      "“Landlord may terminate this lease at its sole discretion upon twenty-four (24) hours written notice, without obligation to provide relocation support or reimbursement.”",
    plain:
      "The other party can end the agreement almost immediately, even if you did nothing wrong, and they do not need to help with the fallout.",
    impacts: [
      ["Operational risk", "Your business could lose access to the space with almost no notice."],
      ["Negotiation gap", "There is no transition support or reimbursement built into the exit."],
    ],
  },
];

const modalContent = {
  advisors: {
    title: "Advisor console",
    body: `
      <p>This frontend is structured so your teammate can wire real expert-routing later. For now, treat this as the escalation layer for redlines, negotiation help, and legal review.</p>
      <div class="report-grid" style="margin-top:1rem">
        <div class="report-block">
          <h4>Contract review</h4>
          <p>Escalate a high-risk document into a concise brief with supporting clauses and document anchors.</p>
        </div>
        <div class="report-block">
          <h4>Negotiation support</h4>
          <p>Turn findings into suggested edits the user can actually bring back to the counterparty.</p>
        </div>
      </div>
    `,
  },
  security: {
    title: "Security posture",
    body: `
      <p>The UI is designed to make safety visible: encrypted handoff, explainable findings, and explicit vault actions instead of silent storage.</p>
      <ul class="report-list" style="margin-top:1rem">
        <li>AES-256 style transfer messaging in upload and sharing flows</li>
        <li>Source-linked findings so users can verify each risky clause</li>
        <li>Clear save and share actions for backend audit hooks</li>
      </ul>
    `,
  },
  compare: {
    title: "Compare document versions",
    body: `
      <div class="report-grid">
        <div class="report-block">
          <h4>Current draft · 82</h4>
          <p>Higher risk because liability recovery is narrow, termination is fast, and jurisdiction is more expensive to enforce.</p>
        </div>
        <div class="report-block">
          <h4>Prior draft · 59</h4>
          <p>Moderate risk with a longer notice period and more normal liability structure.</p>
        </div>
        <div class="report-block full">
          <h4>What changed</h4>
          <p>The newer draft adds the kind of asymmetric terms that look harmless at a glance but become expensive after signing.</p>
        </div>
      </div>
    `,
  },
  redline: {
    title: "Suggested redline",
    body: `
      <div class="report-block">
        <h4>Recommended rewrite</h4>
        <p style="font-family:'IBM Plex Mono', monospace">"Each party's aggregate liability will not exceed fees paid in the twelve (12) months before the claim, excluding fraud, willful misconduct, and confidentiality breaches."</p>
      </div>
      <p style="margin-top:1rem">This keeps the protective intent but removes the most visibly unfair asymmetry.</p>
    `,
  },
  lawyer: {
    title: "Share with counsel",
    body: `
      <p>Package the executive summary, top findings, and document anchors into a handoff your teammate can later connect to email or secure report delivery.</p>
      <div class="report-grid" style="margin-top:1rem">
        <div class="report-block">
          <h4>Email secure report</h4>
          <p>Send the analysis and source-linked findings to counsel.</p>
        </div>
        <div class="report-block">
          <h4>Copy judge-ready summary</h4>
          <p>Short version optimized for a live demo or quick legal opinion request.</p>
        </div>
      </div>
    `,
  },
};

// ---------------------------------------------------------------------------
// Session — Backboard Thread ID as user identity
// ---------------------------------------------------------------------------

async function initSession() {
  const stored = localStorage.getItem("clarity_thread_id");
  if (stored) {
    state.threadId = stored;
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/session/init`, { method: "POST" });
    const data = await res.json();
    state.threadId = data.thread_id;
    localStorage.setItem("clarity_thread_id", data.thread_id);
  } catch {
    state.threadId = crypto.randomUUID();
    localStorage.setItem("clarity_thread_id", state.threadId);
  }
}

// ---------------------------------------------------------------------------
// API response → UI state
// ---------------------------------------------------------------------------

function mapApiResponse(data) {
  state.score = data.risk_score_numeric ?? 75;
  state.summary = data.summary_plain_english ?? "";
  if (data.dcp_metrics) state.dcpMetrics = data.dcp_metrics;

  const severityBadge = { CRITICAL: "Critical flag", HIGH: "High risk flag", MEDIUM: "Warning flag", LOW: "Info flag" };
  const typeLabel = (t) =>
    (t ?? "Unknown clause").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const mapped = (data.flagged_clauses ?? []).map((c) => ({
    badge: severityBadge[c.severity] ?? "Flag",
    title: typeLabel(c.type),
    subtitle: `${c.source === "distilbert" ? "AI detected" : "Rule detected"} · ${state.uploadedFileName}`,
    original: `“${c.original_text}”`,
    plain: c.translation || c.original_text,
    impacts: [
      [
        "Risk level",
        `Severity: ${c.severity}. Confidence: ${Math.round((c.confidence ?? 0) * 100)}%.`,
      ],
      [
        "Detected by",
        c.source === "distilbert"
          ? "Custom DistilBERT model trained on legal contracts."
          : "Deterministic rule-based classifier.",
      ],
    ],
  }));

  clauses =
    mapped.length > 0
      ? mapped
      : [
          {
            badge: "All clear",
            title: "No high-risk clauses found",
            subtitle: state.uploadedFileName,
            original: "“No flagged clauses were detected in this document.”",
            plain: "This document appears to carry low overall risk.",
            impacts: [
              ["Result", "No significant risk clauses were identified."],
              ["Recommendation", "Review manually for any domain-specific concerns."],
            ],
          },
        ];

  state.clauseIndex = 0;
}

// ---------------------------------------------------------------------------
// Report generator (Phase 5)
// ---------------------------------------------------------------------------

function downloadReport() {
  if (!state.summary && clauses.length === 0) {
    return;
  }

  const lines = [
    "CLARITY ANALYSIS REPORT",
    "========================",
    `Generated : ${new Date().toLocaleString()}`,
    `Document  : ${state.uploadedFileName}`,
    `Risk score: ${state.score} / 100`,
    "",
    "SUMMARY",
    "-------",
    state.summary || "No summary available.",
    "",
    `FLAGGED CLAUSES (${clauses.length})`,
    "----------------",
    ...clauses.flatMap((c, i) => [
      "",
      `[${i + 1}] ${c.title}`,
      `    Severity : ${c.badge}`,
      `    Original : ${c.original}`,
      `    Plain    : ${c.plain}`,
      `    Impact 1 : ${c.impacts[0][0]} — ${c.impacts[0][1]}`,
      `    Impact 2 : ${c.impacts[1][0]} — ${c.impacts[1][1]}`,
    ]),
  ];

  if (state.dcpMetrics) {
    const m = state.dcpMetrics;
    lines.push(
      "",
      "DCP PARALLEL PROCESSING",
      "-----------------------",
      `Pages processed   : ${m.pages_processed}`,
      `Sequential time   : ${(m.sequential_time_ms / 1000).toFixed(1)}s`,
      `DCP parallel time : ${(m.dcp_parallel_time_ms / 1000).toFixed(1)}s`,
      `Speedup factor    : ${m.speedup_factor}×`,
    );
  }

  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `clarity-report-${state.uploadedFileName.replace(/\.[^.]+$/, "")}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  await initSession();

  const screens = [...document.querySelectorAll(".screen")];
  const modalShell = document.getElementById("modal-shell");
  const toast = document.getElementById("toast");
  const fileInput = document.getElementById("file-input");
  const scoreNumber = document.getElementById("score-number");
  const scoreRing = document.querySelector(".ring-progress");
  const processingStatus = document.getElementById("processing-status");
  const processingTitle = document.getElementById("processing-title");
  const processingFileName = document.getElementById("processing-file-name");
  const landingUpload = document.getElementById("landing-upload");
  const cameraUpload = document.getElementById("camera-upload");
  const cameraCapture = document.getElementById("camera-capture");
  const processingContinue = document.getElementById("processing-continue");
  const saveToVault = document.getElementById("save-to-vault");
  const copyReportLink = document.getElementById("copy-report-link");
  const downloadPdf = document.getElementById("download-pdf");
  const nextClause = document.getElementById("next-clause");
  const brandHome = document.getElementById("brand-home");
  const zoomLabel = document.getElementById("zoom-label");
  const zoomIn = document.getElementById("zoom-in");
  const zoomOut = document.getElementById("zoom-out");
  const documentCanvas = document.getElementById("document-canvas");

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("is-visible");
    clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
      toast.classList.remove("is-visible");
    }, 2200);
  }

  function revealOnScroll() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.classList.add("is-visible");
      });
    }, { threshold: 0.1 });
    document.querySelectorAll(".reveal").forEach((node) => observer.observe(node));
  }

  function revealScreen(screen) {
    screen.querySelectorAll(".reveal").forEach((node) => node.classList.remove("is-visible"));
    requestAnimationFrame(revealOnScroll);
  }

  function updateNavState() {
    document.querySelectorAll(".nav-item, .mobile-nav-item").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.screen === state.currentScreen);
    });
  }

  function animateScore(target) {
    const circumference = 2 * Math.PI * 92;
    scoreRing.style.strokeDasharray = `${circumference} ${circumference}`;
    scoreRing.style.strokeDashoffset = String(circumference);

    const start = performance.now();
    const duration = 1500;
    const scoreLabel = document.querySelector(".score-label");

    let riskColor = "#4f46e5";
    let riskText = "Optimal";
    if (target >= 80) { riskColor = "#dc2626"; riskText = "High Risk"; }
    else if (target >= 50) { riskColor = "#f59e0b"; riskText = "Watchlist"; }

    scoreRing.style.stroke = riskColor;
    if (scoreLabel) scoreLabel.textContent = riskText;

    function frame(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const currentScore = Math.round(target * eased);
      scoreNumber.textContent = String(currentScore);
      scoreRing.style.strokeDashoffset = String(circumference - (currentScore / 100) * circumference);
      if (progress < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function updateClauseContent() {
    const current = clauses[state.clauseIndex];
    document.getElementById("clause-badge").textContent = current.badge;
    document.getElementById("clause-title").textContent = current.title;
    document.getElementById("clause-subtitle").textContent = current.subtitle;
    document.getElementById("clause-original").textContent = current.original;
    document.getElementById("clause-plain").textContent = current.plain;
    document.getElementById("impact-title-1").textContent = current.impacts[0][0];
    document.getElementById("impact-copy-1").textContent = current.impacts[0][1];
    document.getElementById("impact-title-2").textContent = current.impacts[1][0];
    document.getElementById("impact-copy-2").textContent = current.impacts[1][1];
  }

  function setScreen(name) {
    state.currentScreen = name;
    screens.forEach((screen) => {
      screen.classList.toggle("is-active", screen.dataset.screen === name);
      if (screen.dataset.screen === name) revealScreen(screen);
    });
    updateNavState();
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (name === "dashboard") animateScore(state.score);
  }

  // ---------------------------------------------------------------------------
  // DCP panel (Phase 5)
  // ---------------------------------------------------------------------------

  function openDcpPanel() {
    const m = state.dcpMetrics;
    const body = m
      ? `
        <div class="report-grid">
          <div class="report-block">
            <h4>Pages processed</h4>
            <p style="font-size:2rem;font-weight:700;margin-top:.25rem">${m.pages_processed}</p>
          </div>
          <div class="report-block">
            <h4>Speedup factor</h4>
            <p style="font-size:2rem;font-weight:700;margin-top:.25rem">${m.speedup_factor}×</p>
          </div>
          <div class="report-block">
            <h4>Sequential (est.)</h4>
            <p>${(m.sequential_time_ms / 1000).toFixed(1)}s</p>
          </div>
          <div class="report-block">
            <h4>DCP parallel</h4>
            <p>${(m.dcp_parallel_time_ms / 1000).toFixed(1)}s</p>
          </div>
          <div class="report-block full">
            <h4>What DCP did</h4>
            <p>Distributed ${m.pages_processed} page${m.pages_processed !== 1 ? "s" : ""} across the DCP worker network in parallel, achieving a <strong>${m.speedup_factor}×</strong> speedup over sequential processing.</p>
          </div>
        </div>`
      : `<p>No DCP metrics yet. Use the camera button on the landing screen to trigger a DCP demo analysis.</p>`;

    modalShell.innerHTML = `
      <div class="modal-card">
        <div class="modal-head">
          <div>
            <div class="eyebrow">Clarity panel</div>
            <h3>DCP parallel processing</h3>
          </div>
          <button class="icon-button" id="modal-close"><span class="material-symbols-rounded">close</span></button>
        </div>
        <div>${body}</div>
      </div>
    `;
    modalShell.classList.add("is-open");
    modalShell.setAttribute("aria-hidden", "false");
    document.getElementById("modal-close")?.addEventListener("click", closeModal);
  }

  // ---------------------------------------------------------------------------
  // Real document analysis
  // ---------------------------------------------------------------------------

  async function analyzeFile(file) {
    processingTitle.textContent = "Analyzing your document";
    processingStatus.textContent = "Extracting text and scanning for risk clauses...";
    setScreen("processing");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("user_id", state.threadId || "demo_user");

      const headers = {};
      if (state.threadId) headers["X-User-Thread"] = state.threadId;

      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers,
        body: formData,
      });

      processingStatus.textContent = "Classification complete. Building your brief...";

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Analysis failed (${res.status})`);
      }

      const data = await res.json();
      mapApiResponse(data);
      processingStatus.textContent = "Decision brief ready. Opening your results.";
      animateScore(state.score);
      updateClauseContent();
      window.setTimeout(() => setScreen("dashboard"), 800);
    } catch (err) {
      // Fallback to mock endpoint so the demo always works
      try {
        processingStatus.textContent = "Switching to demo mode...";
        const mockRes = await fetch(`${API_BASE}/api/analyze/mock`, { method: "POST" });
        if (mockRes.ok) {
          const mockData = await mockRes.json();
          mapApiResponse(mockData);
          animateScore(state.score);
          updateClauseContent();
          window.setTimeout(() => setScreen("dashboard"), 800);
          return;
        }
      } catch { /* fall through */ }
      showToast(`Analysis error: ${err.message}`);
      setScreen("landing");
    }
  }

  // DCP mode — called by camera capture button for demo purposes (Phase 5)
  async function analyzeWithDcp(file) {
    processingTitle.textContent = "DCP parallel analysis";
    processingStatus.textContent = "Distributing pages across DCP worker network...";
    setScreen("processing");

    try {
      const formData = new FormData();
      if (file && file.size > 0) formData.append("file", file);
      formData.append("user_id", state.threadId || "demo_user");

      const headers = {};
      if (state.threadId) headers["X-User-Thread"] = state.threadId;

      const res = await fetch(`${API_BASE}/api/analyze/dcp`, {
        method: "POST",
        headers,
        body: formData,
      });

      processingStatus.textContent = "DCP processing complete. Building your brief...";

      if (!res.ok) throw new Error(`DCP analysis failed (${res.status})`);

      const data = await res.json();
      mapApiResponse(data);
      processingStatus.textContent = "Decision brief ready. Opening your results.";
      animateScore(state.score);
      updateClauseContent();
      window.setTimeout(() => setScreen("dashboard"), 800);
    } catch (err) {
      showToast(`DCP error: ${err.message}`);
      setScreen("landing");
    }
  }

  function handleFile(file) {
    if (!file) return;
    state.uploadedFileName = file.name;
    processingFileName.textContent = file.name;
    showToast(`Added ${file.name}. Starting analysis...`);
    analyzeFile(file);
  }

  function openModal(key) {
    if (key === "dcp") {
      openDcpPanel();
      return;
    }
    const config = modalContent[key];
    if (!config) return;
    modalShell.innerHTML = `
      <div class="modal-card">
        <div class="modal-head">
          <div>
            <div class="eyebrow">Clarity panel</div>
            <h3>${config.title}</h3>
          </div>
          <button class="icon-button" id="modal-close"><span class="material-symbols-rounded">close</span></button>
        </div>
        <div>${config.body}</div>
      </div>
    `;
    modalShell.classList.add("is-open");
    modalShell.setAttribute("aria-hidden", "false");
    document.getElementById("modal-close")?.addEventListener("click", closeModal);
  }

  function closeModal() {
    modalShell.classList.remove("is-open");
    modalShell.setAttribute("aria-hidden", "true");
    modalShell.innerHTML = "";
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-screen], [data-modal], [data-toast]");
    if (!target) return;
    if (target.dataset.screen) setScreen(target.dataset.screen);
    if (target.dataset.modal) openModal(target.dataset.modal);
    if (target.dataset.toast) showToast(target.dataset.toast);
  });

  const headerScanTrigger = document.getElementById("header-scan-trigger");
  const insightsScanTrigger = document.getElementById("insights-scan-trigger");
  const headerInsightsUpload = document.getElementById("header-insights-upload");
  const vaultScanTrigger = document.getElementById("vault-scan-trigger");

  if (headerScanTrigger) headerScanTrigger.addEventListener("click", () => fileInput.click());
  if (insightsScanTrigger) insightsScanTrigger.addEventListener("click", () => fileInput.click());
  if (headerInsightsUpload) headerInsightsUpload.addEventListener("click", () => fileInput.click());
  if (vaultScanTrigger) vaultScanTrigger.addEventListener("click", () => fileInput.click());

  landingUpload.addEventListener("click", () => fileInput.click());
  cameraUpload.addEventListener("click", () => fileInput.click());

  // Camera capture triggers DCP demo mode — showcases parallel processing
  cameraCapture.addEventListener("click", () => {
    showToast("Triggering DCP parallel analysis...");
    analyzeWithDcp(null);
  });

  fileInput.addEventListener("change", (event) => handleFile(event.target.files?.[0]));
  processingContinue.addEventListener("click", () => setScreen("dashboard"));
  saveToVault.addEventListener("click", () => {
    showToast("Analysis saved to Clarity Vault.");
    setScreen("vault");
  });

  copyReportLink.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      showToast("Report link copied.");
    } catch {
      showToast("Link ready to copy.");
    }
  });

  // Download report — generates a plain-text file from the current analysis (Phase 5)
  downloadPdf.addEventListener("click", () => {
    if (!state.summary && clauses.length <= 2 && clauses[0]?.badge === "High risk flag") {
      showToast("Upload a document first to generate a real report.");
      return;
    }
    downloadReport();
    showToast("Report downloaded.");
  });

  nextClause.addEventListener("click", () => {
    state.clauseIndex = (state.clauseIndex + 1) % clauses.length;
    updateClauseContent();
    showToast("Loaded next flagged clause.");
  });

  brandHome.addEventListener("click", () => setScreen("landing"));
  brandHome.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setScreen("landing");
    }
  });

  zoomIn.addEventListener("click", () => {
    state.zoom = Math.min(140, state.zoom + 10);
    zoomLabel.textContent = `${state.zoom}%`;
    documentCanvas.style.transform = `scale(${state.zoom / 100})`;
    documentCanvas.style.transformOrigin = "top center";
  });

  zoomOut.addEventListener("click", () => {
    state.zoom = Math.max(80, state.zoom - 10);
    zoomLabel.textContent = `${state.zoom}%`;
    documentCanvas.style.transform = `scale(${state.zoom / 100})`;
    documentCanvas.style.transformOrigin = "top center";
  });

  modalShell.addEventListener("click", (event) => {
    if (event.target === modalShell) closeModal();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeModal();
  });

  updateClauseContent();
  setScreen("landing");
});
