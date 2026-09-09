/**
 * app.js
 * ------
 * Resumatic frontend — drag-and-drop resume upload, API integration,
 * progress animation, and PDF download.
 */

(() => {
  "use strict";

  // =========================================================================
  // Configuration
  // =========================================================================

  // Connect to current origin if served by FastAPI on port 8000, or fallback to backend at http://localhost:8000
  const API_BASE = (window.location.protocol.startsWith("http") && window.location.port === "8000")
    ? window.location.origin
    : (window.location.protocol.startsWith("http") && window.location.port === ""
      ? window.location.origin
      : "http://localhost:8000");
  const API_ENDPOINT = `${API_BASE}/tailor-resume`;
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
  const ALLOWED_TYPES = new Set([
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ]);
  const ALLOWED_EXTENSIONS = new Set([".pdf", ".docx"]);

  // =========================================================================
  // DOM References
  // =========================================================================

  const $ = (sel) => document.querySelector(sel);

  const dom = {
    form:           $("#tailorForm"),
    dropZone:       $("#dropZone"),
    fileInput:      $("#fileInput"),
    dropIcon:       $("#dropIcon"),
    dropLabel:      $("#dropLabel"),
    filePreview:    $("#filePreview"),
    fileName:       $("#fileName"),
    fileSize:       $("#fileSize"),
    removeFile:     $("#removeFile"),
    fileError:      $("#fileError"),
    jobDescription: $("#jobDescription"),
    charCount:      $("#charCount"),
    jdError:        $("#jdError"),
    submitBtn:      $("#submitBtn"),
    statusArea:     $("#statusArea"),
    processingState:$("#processingState"),
    successState:   $("#successState"),
    errorState:     $("#errorState"),
    errorMessage:   $("#errorMessage"),
    downloadAgain:  $("#downloadAgain"),
    startOver:      $("#startOver"),
    tryAgain:       $("#tryAgain"),
  };

  // =========================================================================
  // State
  // =========================================================================

  let selectedFile = null;
  let resultBlobUrl = null;

  // =========================================================================
  // Utilities
  // =========================================================================

  function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function getFileExtension(name) {
    const idx = name.lastIndexOf(".");
    return idx !== -1 ? name.slice(idx).toLowerCase() : "";
  }

  function showError(el, message) {
    el.textContent = message;
    el.hidden = false;
  }

  function hideError(el) {
    el.textContent = "";
    el.hidden = true;
  }

  // =========================================================================
  // File Validation
  // =========================================================================

  function validateFile(file) {
    if (!file) return "Please select a file.";

    const ext = getFileExtension(file.name);
    const typeOk = ALLOWED_TYPES.has(file.type) || ALLOWED_EXTENSIONS.has(ext);
    if (!typeOk) {
      return `Unsupported file type "${ext || file.type}". Please upload a PDF or DOCX file.`;
    }

    if (file.size > MAX_FILE_SIZE) {
      return `File is too large (${formatFileSize(file.size)}). Maximum size is 10 MB.`;
    }

    return null; // valid
  }

  // =========================================================================
  // File Selection
  // =========================================================================

  function selectFile(file) {
    const error = validateFile(file);
    if (error) {
      showError(dom.fileError, error);
      dom.dropZone.classList.add("drop-zone--error");
      setTimeout(() => dom.dropZone.classList.remove("drop-zone--error"), 2000);
      return;
    }

    hideError(dom.fileError);
    selectedFile = file;

    // Update drop zone appearance
    dom.dropZone.classList.add("drop-zone--has-file");
    dom.dropLabel.textContent = "File selected!";

    // Show file preview
    dom.fileName.textContent = file.name;
    dom.fileSize.textContent = formatFileSize(file.size);
    dom.filePreview.hidden = false;

    updateSubmitButton();
  }

  function removeSelectedFile() {
    selectedFile = null;
    dom.fileInput.value = "";
    dom.dropZone.classList.remove("drop-zone--has-file");
    dom.dropLabel.textContent = "Drop your file here";
    dom.filePreview.hidden = true;
    hideError(dom.fileError);
    updateSubmitButton();
  }

  // =========================================================================
  // Submit Button State
  // =========================================================================

  function updateSubmitButton() {
    const hasFile = selectedFile !== null;
    const hasJD = dom.jobDescription.value.trim().length > 0;
    dom.submitBtn.disabled = !(hasFile && hasJD);
  }

  // =========================================================================
  // Progress Steps Animation
  // =========================================================================

  const STEPS = ["extract", "enhance", "generate"];
  let progressInterval = null;

  function startProgressAnimation() {
    let currentIdx = 0;
    updateProgressStep(currentIdx);

    progressInterval = setInterval(() => {
      // Mark previous as done
      markStepDone(currentIdx);
      currentIdx++;
      if (currentIdx < STEPS.length) {
        updateProgressStep(currentIdx);
      } else {
        clearInterval(progressInterval);
        progressInterval = null;
      }
    }, 8000); // Advance every 8 seconds (pipeline takes ~20-60s)
  }

  function updateProgressStep(idx) {
    const steps = document.querySelectorAll(".progress-step");
    const lines = document.querySelectorAll(".progress-step__line");

    steps.forEach((step, i) => {
      step.classList.remove("progress-step--active", "progress-step--done");
      if (i < idx) step.classList.add("progress-step--done");
      if (i === idx) step.classList.add("progress-step--active");
    });

    lines.forEach((line, i) => {
      line.classList.toggle("progress-step__line--done", i < idx);
    });
  }

  function markStepDone(idx) {
    const steps = document.querySelectorAll(".progress-step");
    const lines = document.querySelectorAll(".progress-step__line");
    if (steps[idx]) {
      steps[idx].classList.remove("progress-step--active");
      steps[idx].classList.add("progress-step--done");
    }
    if (lines[idx]) {
      lines[idx].classList.add("progress-step__line--done");
    }
  }

  function stopProgressAnimation() {
    if (progressInterval) {
      clearInterval(progressInterval);
      progressInterval = null;
    }
    // Mark all as done
    document.querySelectorAll(".progress-step").forEach((s) => {
      s.classList.remove("progress-step--active");
      s.classList.add("progress-step--done");
    });
    document.querySelectorAll(".progress-step__line").forEach((l) => {
      l.classList.add("progress-step__line--done");
    });
  }

  // =========================================================================
  // UI State Machine
  // =========================================================================

  function showState(state) {
    // Hide form when processing or showing results
    const formVisible = state === "idle";
    dom.form.style.display = formVisible ? "" : "none";

    // Show status area for non-idle states
    dom.statusArea.hidden = state === "idle";
    dom.processingState.hidden = state !== "processing";
    dom.successState.hidden = state !== "success";
    dom.errorState.hidden = state !== "error";

    if (state === "processing") {
      startProgressAnimation();
    }
  }

  function resetToIdle() {
    // Clean up blob URL
    if (resultBlobUrl) {
      URL.revokeObjectURL(resultBlobUrl);
      resultBlobUrl = null;
    }

    // Reset progress indicators
    document.querySelectorAll(".progress-step").forEach((s) => {
      s.classList.remove("progress-step--active", "progress-step--done");
    });
    document.querySelectorAll(".progress-step__line").forEach((l) => {
      l.classList.remove("progress-step__line--done");
    });

    showState("idle");

    // Scroll to top
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // =========================================================================
  // API Call & Download
  // =========================================================================

  async function submitResume() {
    if (!selectedFile || !dom.jobDescription.value.trim()) return;

    showState("processing");

    // Scroll to progress
    dom.statusArea.scrollIntoView({ behavior: "smooth", block: "center" });

    const formData = new FormData();
    formData.append("resume", selectedFile);
    formData.append("job_description", dom.jobDescription.value.trim());

    try {
      const response = await fetch(API_ENDPOINT, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let errorText = "An unexpected error occurred. Please try again.";
        try {
          const errorData = await response.json();
          errorText = errorData.detail || errorText;
        } catch {
          errorText = `Server error (${response.status}): ${response.statusText}`;
        }
        // Surface auth/config errors with a clear prefix
        if (response.status === 401) {
          errorText = `⚙️ Configuration error: ${errorText}`;
        }
        throw new Error(errorText);
      }

      // Ensure we got a PDF back (guard against unexpected content types)
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("pdf")) {
        throw new Error("Server returned an unexpected response. Check server logs.");
      }

      // Get the PDF blob
      const blob = await response.blob();
      resultBlobUrl = URL.createObjectURL(blob);

      // Stop progress and show success
      stopProgressAnimation();
      showState("success");

      // Auto-download
      triggerDownload();

    } catch (err) {
      stopProgressAnimation();
      dom.errorMessage.textContent = err.message;
      showState("error");
    }
  }

  function triggerDownload() {
    if (!resultBlobUrl) return;
    const a = document.createElement("a");
    a.href = resultBlobUrl;
    a.download = "tailored_resume.pdf";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // =========================================================================
  // Event Listeners
  // =========================================================================

  // --- Drag & Drop ---
  dom.dropZone.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dom.dropZone.classList.add("drop-zone--active");
  });

  dom.dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dom.dropZone.classList.add("drop-zone--active");
  });

  dom.dropZone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    // Only remove if leaving the drop zone entirely (not entering a child)
    if (!dom.dropZone.contains(e.relatedTarget)) {
      dom.dropZone.classList.remove("drop-zone--active");
    }
  });

  dom.dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dom.dropZone.classList.remove("drop-zone--active");
    const file = e.dataTransfer.files[0];
    if (file) selectFile(file);
  });

  // --- Keyboard activation for drop zone ---
  dom.dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      dom.fileInput.click();
    }
  });

  // --- File input change (click-to-browse) ---
  dom.fileInput.addEventListener("change", () => {
    const file = dom.fileInput.files[0];
    if (file) selectFile(file);
  });

  // --- Remove file ---
  dom.removeFile.addEventListener("click", removeSelectedFile);

  // --- Job description character count ---
  dom.jobDescription.addEventListener("input", () => {
    const len = dom.jobDescription.value.length;
    dom.charCount.textContent = `${len.toLocaleString()} character${len !== 1 ? "s" : ""}`;
    hideError(dom.jdError);
    updateSubmitButton();
  });

  // --- Form submit ---
  dom.form.addEventListener("submit", (e) => {
    e.preventDefault();

    // Final validation
    let valid = true;

    if (!selectedFile) {
      showError(dom.fileError, "Please upload your resume file.");
      valid = false;
    }

    if (!dom.jobDescription.value.trim()) {
      showError(dom.jdError, "Please enter a job description.");
      valid = false;
    }

    if (valid) submitResume();
  });

  // --- Success actions ---
  dom.downloadAgain.addEventListener("click", triggerDownload);
  dom.startOver.addEventListener("click", () => {
    removeSelectedFile();
    dom.jobDescription.value = "";
    dom.charCount.textContent = "0 characters";
    resetToIdle();
  });

  // --- Error action ---
  dom.tryAgain.addEventListener("click", resetToIdle);

  // --- Prevent default drag behavior on the whole page ---
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", (e) => e.preventDefault());

})();
