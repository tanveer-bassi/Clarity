const state = {
  currentScreen: "landing",
  uploadedFileName: "Hospital_Consent_Form.pdf",
  score: 75,
  clauseIndex: 0,
  zoom: 100,
  scoreAnimated: false,
  isProcessing: false,
};

let clauses = [];

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
        <p style="font-family:'IBM Plex Mono', monospace">“Each party’s aggregate liability will not exceed fees paid in the twelve (12) months before the claim, excluding fraud, willful misconduct, and confidentiality breaches.”</p>
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

document.addEventListener("DOMContentLoaded", () => {
  const screens = [...document.querySelectorAll(".screen")];
  const navButtons = [...document.querySelectorAll("[data-screen]")];
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

  let scrollObserver;
  function revealOnScroll() {
    if (!scrollObserver) {
      scrollObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
          }
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -120px 0px" });
    }

    const items = document.querySelectorAll(".reveal:not(.is-visible)");
    items.forEach((node) => {
      scrollObserver.observe(node);
    });
  }

  function revealScreen(screen) {
    revealOnScroll();
  }

  function updateNavState() {
    document.querySelectorAll(".nav-item, .mobile-nav-item").forEach((button) => {
      const active = button.dataset.screen === state.currentScreen;
      button.classList.toggle("is-active", active);
    });
  }

  function getRiskColor(score) {
    const normalized = Math.max(0, Math.min(100, score)) / 100;
    const hue = 8 + (120 - 8) * (1 - normalized);
    const saturation = 88;
    const lightness = 28 + normalized * 24;
    return `hsl(${hue} ${saturation}% ${lightness}%)`;
  }

  function getRiskTextLabel() {
    if (state.riskLabel === "CRITICAL") return "CRITICAL";
    if (state.riskLabel === "HIGH") return "HIGH RISK";
    if (state.riskLabel === "MEDIUM") return "WATCHLIST";
    return "LOW RISK";
  }

  function animateScore(target) {
    const circumference = 2 * Math.PI * 92; // 578.05
    scoreRing.style.strokeDasharray = `${circumference} ${circumference}`;
    scoreRing.style.strokeDashoffset = String(circumference);

    const start = performance.now();
    const duration = 1500;

    const scoreLabel = document.querySelector(".score-label");
    const clampedTarget = Math.max(0, Math.min(100, target));

    if (scoreLabel) scoreLabel.textContent = getRiskTextLabel();

    function frame(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const currentScore = Math.round(clampedTarget * eased);

      scoreNumber.textContent = String(currentScore);

      const offset = circumference - (currentScore / 100) * circumference;
      scoreRing.style.strokeDashoffset = String(offset);
      scoreRing.style.stroke = getRiskColor(currentScore);

      if (progress < 1) requestAnimationFrame(frame);
    }

    state.scoreAnimated = true;
    requestAnimationFrame(frame);
  }

  function renderScore(target) {
    const circumference = 2 * Math.PI * 92;
    const clampedTarget = Math.max(0, Math.min(100, target));
    const normalized = clampedTarget / 100;
    const scoreLabel = document.querySelector(".score-label");

    scoreRing.style.strokeDasharray = `${circumference} ${circumference}`;
    scoreRing.style.strokeDashoffset = String(circumference - normalized * circumference);
    scoreRing.style.stroke = getRiskColor(clampedTarget);
    scoreNumber.textContent = String(clampedTarget);

    if (scoreLabel) {
      scoreLabel.textContent = getRiskTextLabel();
    }
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
    const isNewScreen = state.currentScreen !== name;
    state.currentScreen = name;

    // Only scroll to top if we are actually switching to a different section
    if (isNewScreen) {
      window.scrollTo(0, 0);
    }

    screens.forEach((screen) => {
      screen.classList.toggle("is-active", screen.dataset.screen === name);
      if (screen.dataset.screen === name) revealScreen(screen);
    });
    updateNavState();

    if (name === "dashboard") {
      if (state.scoreAnimated) {
        renderScore(state.score);
      } else {
        animateScore(state.score);
      }
    }
  }

  const API_BASE = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

  async function callAnalyzeMock() {
    const endpoint = `${API_BASE}/api/analyze/mock`;
    console.log(`[Clarity] Calling mock endpoint: ${endpoint}`);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log("[Clarity] Mock response JSON:", data);
      return data;
    } catch (error) {
      console.error("[Clarity] API call failed:", error);
      throw error;
    }
  }

  async function callAnalyzeReal(file) {
    const endpoint = `${API_BASE}/api/analyze`;
    console.log(`[Clarity] Calling real endpoint: ${endpoint}`);
    console.log(`[Clarity] Uploading file: ${file.name}`);
    
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log("[Clarity] Real response JSON:", data);
      return data;
    } catch (error) {
      console.error("[Clarity] Real API call failed:", error);
      throw error;
    }
  }

  function mapApiResponse(data) {
    state.score = data.risk_score_numeric;
    state.riskLabel = data.overall_risk_score;
    
    console.log("[Clarity DEBUG] raw response JSON:", data);
    console.log("[Clarity DEBUG] parsed risk_score_numeric:", state.score);
    console.log("[Clarity DEBUG] rendered score value (target):", state.score);
    console.log("[Clarity DEBUG] overall_risk_score:", state.riskLabel);
    console.log("[Clarity DEBUG] flagged_clauses.length:", data.flagged_clauses ? data.flagged_clauses.length : 0);
    
    // Update headline based on overall score
    const headline = document.getElementById("discovery-headline");
    const summary = document.getElementById("discovery-summary");
    
    if (headline) {
      if (data.overall_risk_score === "CRITICAL") {
          headline.textContent = "Critical Risk Detected";
      } else if (data.overall_risk_score === "HIGH") {
          headline.textContent = "High-Risk Exposure Detected";
      } else if (data.overall_risk_score === "MEDIUM") {
          headline.textContent = "Moderate Risk Detected";
      } else {
          headline.textContent = "Low Risk / No Major Issues Detected";
      }
    }
        
    if (summary) {
      summary.textContent = data.summary_plain_english || "No summary provided.";
    }

    const flaggedCount = data.flagged_clauses ? data.flagged_clauses.length : 0;
    const criticalCount = data.flagged_clauses ? data.flagged_clauses.filter(c => c.severity === "CRITICAL").length : 0;
    
    const criticalFlagsCount = document.getElementById("critical-flags-count");
    if (criticalFlagsCount) criticalFlagsCount.textContent = `${criticalCount} Critical Flags`;
    
    const criticalPill = document.getElementById("critical-flags-pill");
    if (criticalPill) {
        if (criticalCount > 0) {
            criticalPill.classList.add("red", "active");
        } else {
            criticalPill.classList.remove("red", "active");
        }
    }
    
    const standardClausesCount = document.getElementById("standard-clauses-count");
    if (standardClausesCount) standardClausesCount.textContent = `${flaggedCount} Total Flags`;

    const findingsGrid = document.getElementById("findings-grid");
    if (findingsGrid) {
        findingsGrid.innerHTML = "";
        
        if (data.flagged_clauses && data.flagged_clauses.length > 0) {
            data.flagged_clauses.slice(0, 4).forEach((clause, i) => {
                const article = document.createElement("article");
                article.className = `finding-card reveal reveal-delay-${i + 1}`;
                
                let riskClass = "caution";
                if (clause.severity === "CRITICAL") riskClass = "critical";
                else if (clause.severity === "HIGH") riskClass = "warning";
                
                if (i === 0 && clause.severity === "CRITICAL") article.classList.add("finding-card-featured", "risk-critical");
                else article.classList.add(`risk-${riskClass}`);
                
                const typeFormat = clause.type.replace(/_/g, " ");
                const typeCap = typeFormat.charAt(0) + typeFormat.slice(1).toLowerCase();
                
                article.innerHTML = `
                    <div class="finding-head">
                        <span class="risk-badge ${riskClass}">${clause.severity.charAt(0) + clause.severity.slice(1).toLowerCase()}</span>
                        <span class="finding-icon" aria-hidden="true">${Math.round(clause.confidence * 100)}%</span>
                    </div>
                    <div class="finding-copy">
                        <h3>${typeCap}</h3>
                        <p class="finding-summary"><strong>Plain English:</strong> ${clause.translation || clause.original_text}</p>
                    </div>
                    <div class="legal-box">“${clause.original_text}”</div>
                    <button class="text-link" data-screen="clause">View full clause</button>
                `;
                
                findingsGrid.appendChild(article);
            });
        } else {
            // Render a safe state card when no flags are found
            const article = document.createElement("article");
            article.className = `finding-card reveal reveal-delay-1 risk-safe`;
            article.innerHTML = `
                <div class="finding-head">
                    <span class="risk-badge safe">Low</span>
                    <span class="finding-icon" aria-hidden="true"><span class="material-symbols-rounded">check_circle</span></span>
                </div>
                <div class="finding-copy">
                    <h3>No risky clauses detected</h3>
                    <p class="finding-summary"><strong>Plain English:</strong> This document appears low risk based on the analyzed text.</p>
                </div>
                <div class="legal-box">“No flagged clauses were detected by the system.”</div>
                <button class="text-link" data-screen="clause">View analysis</button>
            `;
            findingsGrid.appendChild(article);
        }
        
        revealOnScroll();
    }
    
    clauses.length = 0;
    if (data.flagged_clauses) {
        data.flagged_clauses.forEach(c => {
            const typeFormat = c.type.replace(/_/g, " ");
            clauses.push({
                badge: c.severity,
                title: typeFormat.charAt(0) + typeFormat.slice(1).toLowerCase(),
                subtitle: state.uploadedFileName,
                original: `“${c.original_text}”`,
                plain: c.translation || c.original_text,
                impacts: [
                    ["Risk level", `Severity: ${c.severity}. Confidence: ${Math.round(c.confidence * 100)}%.`],
                    ["Detected by", c.source === "distilbert" ? "Custom DistilBERT model trained on legal contracts." : "Deterministic rule-based classifier."]
                ]
            });
        });
    }
    if (clauses.length === 0) {
        clauses.push({
            badge: "All clear", title: "No high-risk clauses found", subtitle: state.uploadedFileName, original: "“No flagged clauses were detected in this document.”", plain: "This document appears to carry low overall risk.", impacts: [["Result", "No significant risk clauses were identified."], ["Recommendation", "Review manually for any domain-specific concerns."]]
        });
    }
    state.clauseIndex = 0;
  }

  async function simulateProcessing() {
    state.scoreAnimated = false;
    processingTitle.textContent = "Analyzing your document";
    processingStatus.textContent = "Connecting to backend and scoring risk...";
    setScreen("processing");

    try {
        const data = await callAnalyzeMock();
        
        processingStatus.textContent = "Drafting plain-English summary...";
        await new Promise(resolve => setTimeout(resolve, 800));

        mapApiResponse(data);
        
        processingStatus.textContent = "Decision brief ready. Opening your results.";
        await new Promise(resolve => setTimeout(resolve, 400));
        
        setScreen("dashboard");
    } catch (error) {
        console.error(error);
        processingStatus.textContent = "Analysis failed. Please try again or check backend.";
        showToast("Error connecting to backend");
        setTimeout(() => setScreen("landing"), 3000);
    }
  }

  async function analyzeFile(file) {
    state.scoreAnimated = false;
    processingTitle.textContent = "Analyzing your document";
    processingStatus.textContent = "Connecting to backend and scoring risk...";
    setScreen("processing");

    try {
        const data = await callAnalyzeReal(file);
        
        processingStatus.textContent = "Drafting plain-English summary...";
        // artificial delay to let user read the status message
        await new Promise(resolve => setTimeout(resolve, 800));

        mapApiResponse(data);
        
        processingStatus.textContent = "Decision brief ready. Opening your results.";
        await new Promise(resolve => setTimeout(resolve, 400));
        
        setScreen("dashboard");
    } catch (error) {
        console.error(error);
        processingStatus.textContent = "Analysis failed. Please try again or check backend.";
        showToast("Error connecting to backend");
        // We do NOT navigate back home instantly.
        // User can click "New Scan" or we can leave a button.
        // For now, the user stays on the processing screen with the error message.
    } finally {
        state.isProcessing = false;
    }
  }

  function handleFile(file) {
    if (!file) return;
    if (state.isProcessing) return; // disable repeated submissions while loading
    state.isProcessing = true;
    
    state.uploadedFileName = file.name;
    processingFileName.textContent = file.name;
    showToast(`Added ${file.name}. Starting analysis...`);
    
    // Call the real endpoint instead of simulateProcessing
    analyzeFile(file);
  }

  function openModal(key) {
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

  // Event Delegation for Navigation and UI Triggers
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-screen], [data-modal], [data-toast]");
    if (!target) return;

    if (target.dataset.screen) setScreen(target.dataset.screen);
    if (target.dataset.modal) openModal(target.dataset.modal);
    if (target.dataset.toast) showToast(target.dataset.toast);
  });

  const headerScanTrigger = document.getElementById("header-scan-trigger");
  const insightsScanTrigger = document.getElementById("insights-scan-trigger");
  const vaultScanTrigger = document.getElementById("vault-scan-trigger");

  if (headerScanTrigger) {
    headerScanTrigger.addEventListener("click", () => fileInput.click());
  }

  if (insightsScanTrigger) {
    insightsScanTrigger.addEventListener("click", () => fileInput.click());
  }



  if (vaultScanTrigger) {
    vaultScanTrigger.addEventListener("click", () => fileInput.click());
  }

  landingUpload.addEventListener("click", () => fileInput.click());
  cameraUpload.addEventListener("click", () => fileInput.click());
  cameraCapture.addEventListener("click", () => {
    showToast("Photo captured. Starting analysis...");
    simulateProcessing();
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

  downloadPdf.addEventListener("click", () => showToast("PDF export hook ready for backend integration."));
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

  // Scroll-sensitive header
  const header = document.querySelector("header");
  if (header) {
    const checkScroll = () => {
      if (window.scrollY > 50) {
        header.classList.add("scrolled");
      } else {
        header.classList.remove("scrolled");
      }
    };
    window.addEventListener("scroll", checkScroll);
    checkScroll(); // Check once on load
  }

  updateClauseContent();
  setScreen("landing");
});
