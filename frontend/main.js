const state = {
  currentScreen: "landing",
  uploadedFileName: "Hospital_Consent_Form.pdf",
  score: 75,
  clauseIndex: 0,
  zoom: 100,
  scoreAnimated: false,
  isProcessing: false,
  lastAnalysisData: null,
  vaultHistory: [],
  dcpActive: false,
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
        <div class="report-block action-block" id="modal-email-report" style="cursor:pointer">
          <h4>Email secure report</h4>
          <p>Send the analysis and source-linked findings to counsel via email.</p>
        </div>
        <div class="report-block action-block" id="modal-copy-summary" style="cursor:pointer">
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
  const copyReportText = document.getElementById("copy-report-text");
  const downloadPdf = document.getElementById("download-pdf");
  const nextClause = document.getElementById("next-clause");
  const brandHome = document.getElementById("brand-home");
  const zoomLabel = document.getElementById("zoom-label");
  const zoomIn = document.getElementById("zoom-in");
  const zoomOut = document.getElementById("zoom-out");
  const documentCanvas = document.getElementById("document-canvas");
  const dcpToggleInput = document.getElementById("dcp-toggle-input");

  if (dcpToggleInput) {
    dcpToggleInput.addEventListener("change", (e) => {
      state.dcpActive = e.target.checked;
      console.log(`[Clarity] DCP mode: ${state.dcpActive}`);
    });
  }

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
    if (name === "report") {
      if (!state.lastAnalysisData) {
        showToast("Please analyze a document first.");
        return;
      }
      generateReport();
    }

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

    if (name === "vault") {
      loadVaultHistory();
    }
  }

  function generateReport() {
    const data = state.lastAnalysisData;
    console.log("[Clarity] generateReport using object:", data);
    document.getElementById("report-title").textContent = state.uploadedFileName || "Document Analysis";
    document.getElementById("report-score-number").textContent = data.risk_score_numeric;
    document.getElementById("report-score-label").textContent = data.overall_risk_score;
    
    let summary = data.summary_plain_english;
    if (!summary) {
      if (data.risk_score_numeric >= 70) {
        summary = "CRITICAL ADVISORY: This document contains significant legal risks. While the detailed summary is unavailable for this specific historical record, the high risk score suggests extreme caution is required.";
      } else {
        summary = "Detailed plain-English summary is unavailable for this historical record.";
      }
    }
    document.getElementById("report-summary").textContent = summary;
    
    // DCP Metrics
    const dcpContainer = document.getElementById("report-dcp-container");
    if (data.dcp_metrics && data.processing_metadata && (data.processing_metadata.used_dcp || data.processing_metadata.dcp_mode)) {
      const dcp = data.dcp_metrics;
      const meta = data.processing_metadata;
      
      dcpContainer.style.display = "block";
      document.getElementById("report-dcp-pages").textContent = dcp.pages_processed;
      document.getElementById("report-dcp-seq").textContent = `${(dcp.sequential_time_ms / 1000).toFixed(1)}s`;
      document.getElementById("report-dcp-para").textContent = `${(dcp.dcp_parallel_time_ms / 1000).toFixed(1)}s`;
      document.getElementById("report-dcp-speedup").textContent = `${dcp.speedup_factor}x`;
      
      document.getElementById("report-dcp-title").textContent = "DCP Parallel Acceleration";
    } else {
      dcpContainer.style.display = "none";
    }
    
    document.getElementById("report-total-flags").textContent = data.flagged_clauses ? data.flagged_clauses.length : 0;
    
    const clausesList = document.getElementById("report-clauses");
    clausesList.innerHTML = "";
    if (data.flagged_clauses && data.flagged_clauses.length > 0) {
      data.flagged_clauses.forEach(c => {
        const li = document.createElement("li");
        li.innerHTML = `<strong>${c.severity}: ${c.type}</strong><br><em>"${c.original_text}"</em><br>Meaning: ${c.translation || "N/A"} (${Math.round(c.confidence*100)}% confidence)`;
        clausesList.appendChild(li);
      });
    } else {
      const li = document.createElement("li");
      li.textContent = "No flags detected.";
      clausesList.appendChild(li);
    }
    
    const metaList = document.getElementById("report-metadata");
    metaList.innerHTML = "";
    if (data.processing_metadata) {
      const meta = data.processing_metadata;
      metaList.innerHTML = `
        <li>OCR Mode: ${meta.ocr_mode || "N/A"}</li>
        <li>Model Source: ${meta.model_source || "N/A"}</li>
        <li>Endpoint Mode: ${meta.endpoint_mode || "N/A"}</li>
        <li>DistilBERT used: ${meta.used_distilbert}</li>
        <li>Google Vision used: ${meta.used_google_vision}</li>
        <li>Gemma used: ${meta.used_gemma}</li>
        <li>Backboard used: ${meta.used_backboard}</li>
        <li>DCP used: ${meta.used_dcp}</li>
        <li>DCP mode: ${meta.dcp_mode || "off"}</li>
      `;
      
      if (data.dcp_metrics) {
        const dcp = data.dcp_metrics;
        metaList.innerHTML += `
          <li>DCP Pages: ${dcp.pages_processed}</li>
          <li>DCP Seq Estimate: ${(dcp.sequential_time_ms / 1000).toFixed(1)}s</li>
          <li>DCP Parallel: ${(dcp.dcp_parallel_time_ms / 1000).toFixed(1)}s</li>
          <li>DCP Speedup: ${dcp.speedup_factor}x</li>
          ${dcp.job_id ? `<li>DCP Job ID: ${dcp.job_id}</li>` : ""}
        `;
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

  async function callAnalyzeReal(file, endpoint = "/api/analyze") {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", "demo_user");

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
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

  async function loadVaultHistory() {
    const endpoint = `${API_BASE}/api/history/demo_user`;
    const container = document.getElementById("vault-list-container");
    if (!container) return;

    console.log(`[Clarity] Fetching vault history: ${endpoint}`);
    
    try {
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error("Could not load vault history.");
      
      const data = await response.json();
      console.log("[Clarity] Vault history response:", data);
      
      // Sort by scanned_at descending (newest first)
      const documents = (data.documents || []).sort((a, b) => {
        const dateA = a.scanned_at ? new Date(a.scanned_at) : 0;
        const dateB = b.scanned_at ? new Date(b.scanned_at) : 0;
        return dateB - dateA;
      });
      state.vaultHistory = documents;

      // Update Stats
      const processedCount = documents.length;
      const highRiskCount = documents.filter(d => 
        d.overall_risk_score === "HIGH" || 
        d.overall_risk_score === "CRITICAL" || 
        d.risk_score_numeric >= 70
      ).length;
      const avgScore = processedCount > 0 
        ? Math.round(documents.reduce((acc, d) => acc + (d.risk_score_numeric || 0), 0) / processedCount) 
        : 0;

      const statProcessed = document.getElementById("vault-stat-processed");
      const statHighRisk = document.getElementById("vault-stat-high-risk");
      const statAvgScore = document.getElementById("vault-stat-avg-score");

      if (statProcessed) statProcessed.textContent = processedCount;
      if (statHighRisk) statHighRisk.textContent = highRiskCount.toString().padStart(2, '0');
      if (statAvgScore) statAvgScore.textContent = `${avgScore}%`;
      
      if (documents.length === 0) {
        container.innerHTML = `
          <div class="empty-vault reveal">
            <p>No saved documents yet. Scan a document to add it to your vault.</p>
          </div>
        `;
        revealScreen(container);
        return;
      }

      // Populate list
      container.innerHTML = documents.map((doc, idx) => {
        const date = doc.scanned_at ? new Date(doc.scanned_at).toLocaleDateString() : "Recent";
        const riskClass = doc.overall_risk_score.toLowerCase();
        const delay = idx > 0 ? `reveal-delay-${idx + 1}` : "";
        
        return `
          <article class="vault-item glass-card reveal ${delay}">
            <div class="vault-item-top">
              <div class="eyebrow vault-kicker">${idx === 0 ? "Latest scan" : "History"}</div>
              <div class="vault-score-badge ${riskClass}">
                <span class="vault-score-number">${doc.risk_score_numeric}</span>
                <span class="vault-score-copy">${doc.overall_risk_score}</span>
              </div>
            </div>
            <div class="vault-info">
              <div class="vault-title">${doc.filename || doc.document_id}</div>
              <div class="vault-meta">Scanned on ${date}</div>
              <p class="vault-summary">This document was analyzed with ${doc.flagged_count} flagged clauses.</p>
            </div>
            <div class="vault-buttons">
              <button class="btn btn-secondary view-vault-details" data-id="${doc.document_id}">View Details</button>
            </div>
          </article>
        `;
      }).join("");

      revealOnScroll();
    } catch (error) {
      console.error("[Clarity] Vault load error:", error);
      container.innerHTML = `
        <div class="error-vault reveal">
          <p>Could not load your vault. Please try again later.</p>
        </div>
      `;
      revealScreen(container);
    }
  }

  function generateReportText() {
    const data = state.lastAnalysisData;
    if (!data) return "";
    
    let text = `Clarity Legal Analysis Report\n`;
    text += `Document: ${state.uploadedFileName || "Document Analysis"}\n`;
    text += `Risk Score: ${data.risk_score_numeric} (${data.overall_risk_score})\n\n`;
    
    let summary = data.summary_plain_english || "No summary provided.";
    if (data.flagged_clauses && data.flagged_clauses.length === 0) {
      summary = "No risky clauses were detected. This does not replace professional legal advice, but no major red flags were found by Clarity.";
    }
    text += `Executive Summary:\n${summary}\n\n`;
    
    text += `Findings Snapshot (${data.flagged_clauses ? data.flagged_clauses.length : 0}):\n`;
    if (data.flagged_clauses && data.flagged_clauses.length > 0) {
      data.flagged_clauses.forEach(c => {
        text += `- ${c.severity}: ${c.type}\n`;
        text += `  "${c.original_text}"\n`;
        text += `  Meaning: ${c.translation || "N/A"} (${Math.round(c.confidence*100)}% confidence)\n\n`;
      });
    } else {
      text += `- No flags detected.\n\n`;
    }
    
    if (data.processing_metadata) {
      text += `Processing Metadata:\n`;
      const meta = data.processing_metadata;
      text += `- OCR Mode: ${meta.ocr_mode || "N/A"}\n`;
      text += `- Model Source: ${meta.model_source || "N/A"}\n`;
      text += `- Endpoint Mode: ${meta.endpoint_mode || "N/A"}\n`;
      text += `- DistilBERT used: ${meta.used_distilbert}\n`;
      text += `- Google Vision used: ${meta.used_google_vision}\n`;
      text += `- Gemma used: ${meta.used_gemma}\n`;
      text += `- Backboard used: ${meta.used_backboard}\n`;
      text += `- DCP used: ${meta.used_dcp}\n`;
      text += `- DCP mode: ${meta.dcp_mode || "off"}\n`;
      
      if (data.dcp_metrics) {
        const dcp = data.dcp_metrics;
        text += `- DCP Pages: ${dcp.pages_processed}\n`;
        text += `- DCP Seq Estimate: ${(dcp.sequential_time_ms / 1000).toFixed(1)}s\n`;
        text += `- DCP Parallel: ${(dcp.dcp_parallel_time_ms / 1000).toFixed(1)}s\n`;
        text += `- DCP Speedup: ${dcp.speedup_factor}x\n`;
        if (dcp.job_id && dcp.job_id !== "accelerated_fallback" && dcp.job_id !== "simulated") {
          text += `- DCP Job ID: ${dcp.job_id}\n`;
        }
      }
    }
    return text;
  }

  function generateJudgeSummary() {
    const data = state.lastAnalysisData;
    if (!data) return "";
    const flaggedCount = data.flagged_clauses ? data.flagged_clauses.length : 0;
    const criticalCount = data.flagged_clauses ? data.flagged_clauses.filter(c => c.severity === "CRITICAL").length : 0;
    
    let text = `CLARITY EXECUTIVE BRIEF\n`;
    text += `Target: ${state.uploadedFileName}\n`;
    text += `Verdict: ${data.overall_risk_score} (${data.risk_score_numeric}/100)\n`;
    text += `Findings: ${flaggedCount} issues detected, including ${criticalCount} critical red flags.\n\n`;
    text += `Summary: ${data.summary_plain_english || "Document analyzed with no major issues."}\n`;
    return text;
  }

  function mapApiResponse(data) {
    state.lastAnalysisData = data;
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
        const endpoint = state.dcpActive ? "/api/analyze/dcp" : "/api/analyze";
        console.log(`[Clarity] Using endpoint: ${endpoint}`);
        
        if (state.dcpActive) {
            console.log("[Clarity] DCP mode enabled, calling /api/analyze/dcp");
            processingStatus.textContent = "Splitting document into chunks...";
            await new Promise(resolve => setTimeout(resolve, 600));
            processingStatus.textContent = "Offloading to DCP network for parallel analysis...";
            await new Promise(resolve => setTimeout(resolve, 800));
        }

        const data = await callAnalyzeReal(file, endpoint);
        console.log("[Clarity] POST response full keys:", Object.keys(data));
        
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
    
    if (key === "lawyer") {
      document.getElementById("modal-email-report")?.addEventListener("click", () => {
        const data = state.lastAnalysisData;
        if (!data) {
          showToast("No analysis to share.");
          return;
        }
        const subject = encodeURIComponent(`Legal Risk Brief: ${state.uploadedFileName}`);
        const body = encodeURIComponent(generateReportText());
        window.location.href = `mailto:?subject=${subject}&body=${body}`;
      });
      
      document.getElementById("modal-copy-summary")?.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(generateJudgeSummary());
          showToast("Judge-ready summary copied.");
        } catch {
          showToast("Failed to copy summary.");
        }
      });
    }
  }

  function closeModal() {
    modalShell.classList.remove("is-open");
    modalShell.setAttribute("aria-hidden", "true");
    modalShell.innerHTML = "";
  }

  // Event Delegation for Navigation and UI Triggers
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-screen], [data-modal], [data-toast], .view-vault-details");
    if (!target) return;

    if (target.dataset.screen) setScreen(target.dataset.screen);
    if (target.dataset.modal) openModal(target.dataset.modal);
    if (target.dataset.toast) showToast(target.dataset.toast);

    if (target.classList.contains("view-vault-details")) {
      const docId = target.dataset.id;
      console.log(`[Clarity] Vault detail clicked: ${docId}`);
      const doc = state.vaultHistory.find(d => d.document_id === docId);
      console.log("[Clarity] Vault detail selected item:", doc);
      if (doc) {
        state.lastAnalysisData = doc;
        console.log("[Clarity] Normalized vault detail object:", state.lastAnalysisData);
        state.uploadedFileName = doc.filename || "Saved Analysis";
        setScreen("report");
      }
    }
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
    showToast("Analysis saved available in Vault.");
    setScreen("vault");
  });

  copyReportText.addEventListener("click", async () => {
    try {
      const text = generateReportText();
      if (!text) {
        showToast("Please analyze a document first.");
        return;
      }
      await navigator.clipboard.writeText(text);
      showToast("Report copied to clipboard.");
    } catch {
      showToast("Could not copy report.");
    }
  });

  downloadPdf.addEventListener("click", () => {
    const text = generateReportText();
    if (!text) {
      showToast("Please analyze a document first.");
      return;
    }
    
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const safeName = (state.uploadedFileName || "report").replace(/\.[^/.]+$/, "");
    a.href = url;
    a.download = `${safeName}_report.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Report downloaded as .txt");
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
