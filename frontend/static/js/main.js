/**
 * H2S Exposure Monitoring System
 * Clean, human-crafted client controller for strip scanning, real-time inference, and charts.
 */

document.addEventListener("DOMContentLoaded", () => {
  initCameraScanner();
  initDropzone();
  initSampleStrips();
  initDashboardCharts();
  initAttendanceQuickActions();
  initTableFilter();
  initWorkerDeleteHandler();
  initQrBadgeModal();
  initQrAttendanceScanner();
});

// --------------------------------------------------------------------------
// 1. Camera & Scanner Feed (Resilient Multi-Device Controller)
// --------------------------------------------------------------------------
let mediaStream = null;

function initCameraScanner() {
  const videoEl = document.getElementById("camera-video");
  const toggleBtn = document.getElementById("btn-toggle-camera");
  const inlineStartBtn = document.getElementById("btn-camera-inline-start");
  const captureBtn = document.getElementById("btn-capture-frame");
  const cameraContainer = document.getElementById("camera-view-container");
  const fileContainer = document.getElementById("file-view-container");
  const tabCamera = document.getElementById("tab-camera");
  const tabFile = document.getElementById("tab-file");
  const deviceSelect = document.getElementById("camera-device-select");

  if (!videoEl || !toggleBtn) return;

  if (tabCamera && tabFile) {
    tabCamera.addEventListener("click", () => {
      tabCamera.classList.add("active");
      tabFile.classList.remove("active");
      cameraContainer.style.display = "block";
      fileContainer.style.display = "none";
      if (!mediaStream) {
        startCamera();
      }
    });

    tabFile.addEventListener("click", () => {
      tabFile.classList.add("active");
      tabCamera.classList.remove("active");
      cameraContainer.style.display = "none";
      fileContainer.style.display = "block";
      stopCamera();
    });
  }

  toggleBtn.addEventListener("click", () => {
    if (mediaStream) {
      stopCamera();
    } else {
      startCamera();
    }
  });

  if (inlineStartBtn) {
    inlineStartBtn.addEventListener("click", () => startCamera());
  }

  if (deviceSelect) {
    deviceSelect.addEventListener("change", () => {
      if (deviceSelect.value) {
        startCamera(deviceSelect.value);
      }
    });
  }

  if (captureBtn) {
    captureBtn.addEventListener("click", () => {
      if (!mediaStream) {
        showToast("Please activate the camera first.");
        return;
      }
      captureSnapshot();
    });
  }
}

async function startCamera(preferredDeviceId = null) {
  const videoEl = document.getElementById("camera-video");
  const overlay = document.getElementById("camera-overlay-state");
  const stateTitle = document.getElementById("camera-state-title");
  const stateDesc = document.getElementById("camera-state-desc");
  const stateIcon = document.querySelector(".camera-state-icon");
  const inlineStartBtn = document.getElementById("btn-camera-inline-start");
  const toggleBtn = document.getElementById("btn-toggle-camera");
  const captureBtn = document.getElementById("btn-capture-frame");
  const guideBox = document.getElementById("camera-guide");
  const liveBadge = document.getElementById("camera-live-badge");
  const resText = document.getElementById("camera-res-text");

  if (!videoEl) return;

  // 1. Check secure context and mediaDevices availability
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    let errorTitle = "Camera API Not Available";
    let errorDesc = "Your browser has disabled camera access for this page.";

    if (window.isSecureContext === false) {
      errorTitle = "Insecure Connection Blocked Camera";
      errorDesc = "Modern browsers (Chrome, Edge, Safari) strictly require HTTPS or http://localhost to access the camera. If you opened this via a network IP, please use http://localhost:5000.";
    }

    renderCameraError(errorTitle, errorDesc);
    return;
  }

  // 2. Stop any existing track
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop());
    mediaStream = null;
  }

  // 3. Show Loading Overlay
  if (overlay) {
    overlay.style.display = "flex";
    if (stateIcon) {
      stateIcon.className = "camera-state-icon loading";
      stateIcon.innerHTML = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>`;
    }
    if (stateTitle) stateTitle.textContent = "Connecting to Camera...";
    if (stateDesc) stateDesc.textContent = "Requesting device permission and video stream...";
    if (inlineStartBtn) inlineStartBtn.style.display = "none";
  }

  // 4. Construct multi-tier constraints fallback
  const constraintTiers = [];

  if (preferredDeviceId) {
    constraintTiers.push({
      video: {
        deviceId: { exact: preferredDeviceId },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
    constraintTiers.push({
      video: { deviceId: { exact: preferredDeviceId } },
    });
  }

  // High-def environment (mobile rear camera)
  constraintTiers.push({
    video: {
      width: { ideal: 1280 },
      height: { ideal: 720 },
      facingMode: { ideal: "environment" },
    },
  });

  // Standard environment
  constraintTiers.push({
    video: { facingMode: { ideal: "environment" } },
  });

  // Generic desktop 720p
  constraintTiers.push({
    video: { width: { ideal: 1280 }, height: { ideal: 720 } },
  });

  // Ultimate fallback (any camera available)
  constraintTiers.push({ video: true });

  let stream = null;
  let lastError = null;

  for (const constraints of constraintTiers) {
    try {
      console.log("[Camera] Requesting constraints:", constraints);
      stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (stream) break;
    } catch (err) {
      lastError = err;
      console.warn("[Camera] Constraint tier failed:", constraints, err.name, err.message);
      // If user explicitly denied permission, stop cascading
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        break;
      }
    }
  }

  if (!stream) {
    handleCameraError(lastError);
    return;
  }

  // 5. Attach stream to video element
  mediaStream = stream;
  videoEl.srcObject = stream;
  videoEl.setAttribute("playsinline", "");
  videoEl.setAttribute("muted", "");
  videoEl.muted = true;

  const onStreamReady = () => {
    if (overlay) overlay.style.display = "none";
    if (guideBox) guideBox.style.display = "block";
    if (toggleBtn) toggleBtn.textContent = "Stop Camera";
    if (captureBtn) captureBtn.disabled = false;
    if (liveBadge) {
      liveBadge.style.display = "inline-flex";
      if (resText) {
        const w = videoEl.videoWidth || 1280;
        const h = videoEl.videoHeight || 720;
        resText.textContent = `Live Feed Connected (${w}×${h})`;
      }
    }
  };

  try {
    await videoEl.play();
    onStreamReady();
  } catch (playErr) {
    console.warn("[Camera] video.play() deferred to loadeddata:", playErr);
    videoEl.onloadeddata = async () => {
      try {
        await videoEl.play();
        onStreamReady();
      } catch (e) {
        console.error("[Camera] video.play() failed:", e);
      }
    };
  }

  // Enumerate cameras to populate device dropdown if multiple available
  await updateCameraDeviceList(stream);
}

function handleCameraError(err) {
  let title = "Camera Not Connected";
  let desc = "Could not initialize video feed. You can use the 'Upload File' tab to select a strip photo.";

  if (!err) {
    title = "No Camera Detected";
    desc = "No active video stream could be opened. Use the 'Upload File' tab to submit a photo.";
  } else if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
    title = "Camera Permission Denied";
    desc = "Permission was blocked by your browser. Click the lock or camera icon in your address bar to allow camera access, then click 'Retry Camera'.";
  } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
    title = "No Camera Hardware Detected";
    desc = "No webcam was found on this device. Please connect a webcam or use the 'Upload File' tab.";
  } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
    title = "Camera In Use by Another Application";
    desc = "Your webcam is currently locked by another program (e.g. Zoom, Teams, Skype, or another tab). Close other programs and retry.";
  } else if (err.name === "OverconstrainedError") {
    title = "Resolution Not Supported";
    desc = "The requested camera resolution is not supported by your hardware.";
  } else if (err.name === "SecurityError") {
    title = "Insecure Context Blocked";
    desc = "Browsers require HTTPS or http://localhost to access the camera. Open this app on http://localhost:5000.";
  } else {
    title = "Camera Error";
    desc = err.message || err.name || "Failed to access webcam.";
  }

  renderCameraError(title, desc);
}

function renderCameraError(title, desc) {
  const overlay = document.getElementById("camera-overlay-state");
  const stateTitle = document.getElementById("camera-state-title");
  const stateDesc = document.getElementById("camera-state-desc");
  const stateIcon = document.querySelector(".camera-state-icon");
  const inlineStartBtn = document.getElementById("btn-camera-inline-start");
  const toggleBtn = document.getElementById("btn-toggle-camera");
  const guideBox = document.getElementById("camera-guide");
  const liveBadge = document.getElementById("camera-live-badge");

  if (guideBox) guideBox.style.display = "none";
  if (liveBadge) liveBadge.style.display = "none";
  if (toggleBtn) toggleBtn.textContent = "Start Camera";

  if (overlay) {
    overlay.style.display = "flex";
    if (stateIcon) {
      stateIcon.className = "camera-state-icon error";
      stateIcon.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    }
    if (stateTitle) stateTitle.textContent = title;
    if (stateDesc) stateDesc.textContent = desc;
    if (inlineStartBtn) {
      inlineStartBtn.textContent = "Retry Camera";
      inlineStartBtn.style.display = "inline-flex";
    }
  }

  showToast(`${title}: ${desc}`);
}

function stopCamera() {
  const videoEl = document.getElementById("camera-video");
  const overlay = document.getElementById("camera-overlay-state");
  const stateTitle = document.getElementById("camera-state-title");
  const stateDesc = document.getElementById("camera-state-desc");
  const stateIcon = document.querySelector(".camera-state-icon");
  const inlineStartBtn = document.getElementById("btn-camera-inline-start");
  const toggleBtn = document.getElementById("btn-toggle-camera");
  const guideBox = document.getElementById("camera-guide");
  const liveBadge = document.getElementById("camera-live-badge");

  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop());
    mediaStream = null;
  }
  if (videoEl) videoEl.srcObject = null;
  if (guideBox) guideBox.style.display = "none";
  if (liveBadge) liveBadge.style.display = "none";
  if (toggleBtn) toggleBtn.textContent = "Start Camera";

  if (overlay) {
    overlay.style.display = "flex";
    if (stateIcon) {
      stateIcon.className = "camera-state-icon";
      stateIcon.innerHTML = `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>`;
    }
    if (stateTitle) stateTitle.textContent = "Camera Stream Paused";
    if (stateDesc) stateDesc.textContent = "Click 'Start Camera' to resume live optical inspection.";
    if (inlineStartBtn) {
      inlineStartBtn.textContent = "Start Camera";
      inlineStartBtn.style.display = "inline-flex";
    }
  }
}

async function updateCameraDeviceList(activeStream) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices.filter(d => d.kind === "videoinput");
    const selectWrap = document.getElementById("camera-select-wrap");
    const select = document.getElementById("camera-device-select");

    if (!select || videoDevices.length <= 1) {
      if (selectWrap) selectWrap.style.display = "none";
      return;
    }

    let activeDeviceId = null;
    if (activeStream) {
      const track = activeStream.getVideoTracks()[0];
      if (track && track.getSettings) {
        activeDeviceId = track.getSettings().deviceId;
      }
    }

    select.innerHTML = "";
    videoDevices.forEach((dev, index) => {
      const opt = document.createElement("option");
      opt.value = dev.deviceId;
      opt.textContent = dev.label || `Camera ${index + 1}`;
      if (activeDeviceId && dev.deviceId === activeDeviceId) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });

    if (selectWrap) selectWrap.style.display = "block";
  } catch (err) {
    console.warn("[Camera] Device enumeration warning:", err);
  }
}

function captureSnapshot() {
  const videoEl = document.getElementById("camera-video");
  if (!mediaStream || !videoEl) {
    showToast("Please activate the camera first.");
    return;
  }

  const vw = videoEl.videoWidth;
  const vh = videoEl.videoHeight;
  if (!vw || !vh || vw === 0 || vh === 0) {
    showToast("Camera is still warming up. Please wait 1 second and click again.");
    return;
  }

  const canvas = document.createElement("canvas");
  canvas.width = vw;
  canvas.height = vh;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(videoEl, 0, 0, vw, vh);

  const base64Data = canvas.toDataURL("image/jpeg", 0.95);
  submitAnalysis({ image_base64: base64Data });
}

// --------------------------------------------------------------------------
// 2. File Upload & Dropzone
// --------------------------------------------------------------------------
function initDropzone() {
  const dropzone = document.getElementById("upload-dropzone");
  const fileInput = document.getElementById("strip-file-input");
  const form = document.getElementById("exposure-form");

  if (!dropzone || !fileInput) return;

  const browseBtn = document.getElementById("btn-browse-file");
  const deviceSnapBtn = document.getElementById("btn-device-snap");
  const cameraInput = document.getElementById("strip-camera-direct");

  dropzone.addEventListener("click", () => fileInput.click());

  if (browseBtn) {
    browseBtn.addEventListener("click", (e) => {
      e.preventDefault();
      fileInput.click();
    });
  }

  if (deviceSnapBtn && cameraInput) {
    deviceSnapBtn.addEventListener("click", (e) => {
      e.preventDefault();
      cameraInput.click();
    });

    cameraInput.addEventListener("change", () => {
      if (cameraInput.files && cameraInput.files.length > 0) {
        fileInput.files = cameraInput.files;
        handleFileSelected(cameraInput.files[0]);
      }
    });
  }

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!fileInput.files || fileInput.files.length === 0) {
        showToast("Please choose or drag a strip photo first.");
        return;
      }
      const formData = new FormData(form);
      submitAnalysisFormData(formData);
    });
  }
}

function handleFileSelected(file) {
  const preview = document.getElementById("selected-file-preview");
  const wrapper = document.getElementById("preview-wrapper");
  const dropzoneText = document.getElementById("dropzone-text");
  if (preview && file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      preview.src = e.target.result;
      if (wrapper) wrapper.style.display = "block";
      if (dropzoneText) dropzoneText.textContent = `Selected: ${file.name}`;
    };
    reader.readAsDataURL(file);
  }
}

// --------------------------------------------------------------------------
// 3. Test Presets
// --------------------------------------------------------------------------
function initSampleStrips() {
  const stripButtons = document.querySelectorAll(".strip-item-card");
  stripButtons.forEach(btn => {
    btn.addEventListener("click", async () => {
      const cls = btn.dataset.class;
      const imageUrl = btn.dataset.imageUrl;
      const workerSelect = document.getElementById("worker-select");
      const workerId = workerSelect ? workerSelect.value : "1";

      showToast(`Loading test sample...`);

      try {
        const response = await fetch(imageUrl);
        const blob = await response.blob();
        const reader = new FileReader();
        reader.onloadend = () => {
          submitAnalysis({
            image_base64: reader.result,
            worker_id: workerId,
          });
        };
        reader.readAsDataURL(blob);
      } catch (err) {
        showToast("Failed to load test sample.");
      }
    });
  });
}

// --------------------------------------------------------------------------
// 4. Analysis Submission & Result Render
// --------------------------------------------------------------------------
async function submitAnalysis(payload) {
  const workerSelect = document.getElementById("worker-select");
  if (workerSelect && !payload.worker_id) {
    payload.worker_id = workerSelect.value;
  }
  if (!payload.worker_id) {
    showToast("Please select a worker first.");
    return;
  }

  showLoading(true);

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    showLoading(false);

    if (data.success) {
      renderResult(data.diagnosis, data.reading);
      showToast("Analysis complete.");
    } else {
      showToast(data.error || "Analysis failed.");
    }
  } catch (err) {
    showLoading(false);
    showToast("Network error while analyzing image.");
  }
}

async function submitAnalysisFormData(formData) {
  showLoading(true);
  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    showLoading(false);

    if (data.success) {
      renderResult(data.diagnosis, data.reading);
      showToast("Analysis complete.");
    } else {
      showToast(data.error || "Analysis failed.");
    }
  } catch (err) {
    showLoading(false);
    showToast("Network error while uploading image.");
  }
}

function showLoading(isLoading) {
  const btn = document.getElementById("btn-submit-analyze");
  if (btn) {
    btn.disabled = isLoading;
    btn.textContent = isLoading ? "Analyzing paper..." : "Analyze Test Strip";
  }
}

function renderResult(diag, reading) {
  const container = document.getElementById("ai-result-panel");
  if (!container) return;

  let statusClass = "safe";
  let badgeText = "Safe — No Exposure";
  let gaugePct = 6;
  let hazardIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

  if (diag.predicted_class === "low") {
    statusClass = "low";
    badgeText = "Action Level — Low";
    gaugePct = 32;
    hazardIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
  } else if (diag.predicted_class === "medium") {
    statusClass = "medium";
    badgeText = "Warning — Moderate Hazard";
    gaugePct = 65;
    hazardIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
  } else if (diag.predicted_class === "high") {
    statusClass = "high";
    badgeText = "Danger — Critical Excursion";
    gaugePct = 94;
    hazardIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
  }

  container.innerHTML = `
    <div class="result-box">
      <div class="result-banner ${statusClass}">
        <div style="display: flex; align-items: center; gap: 10px;">
          <div class="result-banner-icon">${hazardIcon}</div>
          <div>
            <span style="font-weight: 700; font-size: 14.5px; letter-spacing: -0.2px;">${badgeText}</span>
            <div style="font-size: 12px; opacity: 0.9; margin-top: 1px;">${diag.hazard.title}</div>
          </div>
        </div>
        <span class="badge badge-${statusClass}">
          ${diag.hazard.level}
        </span>
      </div>

      <!-- Chemical Exposure Gauge / Spectrum Meter -->
      <div class="spectrum-meter">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px;">
          <span style="display: flex; align-items: center; gap: 5px;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            Colorimetric Calibration Spectrum
          </span>
          <strong style="color: var(--text-main);">${diag.ppm_formatted}</strong>
        </div>
        <div class="spectrum-bar-track">
          <div class="spectrum-indicator" style="left: ${gaugePct}%;"></div>
        </div>
        <div class="spectrum-labels">
          <span>0 ppm (Safe)</span>
          <span>1.0 ppm (TWA)</span>
          <span>5.0 ppm (STEL)</span>
          <span>15+ ppm (Ceiling)</span>
        </div>
      </div>

      <div class="metrics-row">
        <div class="metric-item">
          <div class="lbl">Estimated H₂S Level</div>
          <div class="val">${diag.ppm_formatted}</div>
          <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 3px;">${diag.hazard.osha_status}</div>
        </div>

        <div class="metric-item">
          <div class="lbl">Optical Confidence</div>
          <div class="val">${diag.confidence_pct}%</div>
          <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 3px;">Inference: ${diag.inference_time_ms} ms (CPU)</div>
        </div>
      </div>

      <div class="safety-action-card">
        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 5px; font-size: 12.5px; font-weight: 700; color: var(--text-main);">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
          Mandatory Safety Protocol:
        </div>
        <div style="font-size: 13px; line-height: 1.45; color: var(--text-secondary);">
          ${diag.hazard.recommendation}
        </div>
      </div>
    </div>
  `;

  // Prepend to history table if on page
  const tbody = document.getElementById("reading-history-tbody");
  if (tbody) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span style="color: var(--text-muted); font-size: 12px;">${reading.timestamp.replace("T", " ").substring(11, 16)}</span></td>
      <td><span class="badge badge-${statusClass}"><span class="badge-dot"></span> ${reading.predicted_class}</span></td>
      <td><strong>${diag.ppm_formatted}</strong></td>
      <td>${diag.confidence_pct}%</td>
      <td><a href="/static/${reading.image_path}" target="_blank" class="btn btn-sm btn-secondary">View</a></td>
    `;
    tbody.prepend(tr);
  }
}

// --------------------------------------------------------------------------
// 5. Dashboard Activity Chart
// --------------------------------------------------------------------------
async function initDashboardCharts() {
  const canvas = document.getElementById("hourlyTrendChart");
  if (!canvas || typeof Chart === "undefined") return;

  try {
    const res = await fetch("/api/stats");
    const data = await res.json();

    new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: ["8am", "9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm"],
        datasets: [
          {
            label: "Scans",
            data: (data.hourly_counts || []).slice(8, 18),
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.06)",
            borderWidth: 2,
            fill: true,
            tension: 0.25,
            pointRadius: 3,
            pointBackgroundColor: "#2563eb",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#94a3b8", font: { size: 11 } },
          },
          y: {
            beginAtZero: true,
            grid: { color: "#f1f5f9" },
            ticks: { color: "#94a3b8", font: { size: 11 }, stepSize: 1 },
          },
        },
      },
    });
  } catch (err) {
    console.error("Chart error:", err);
  }
}

// --------------------------------------------------------------------------
// 6. Attendance Quick Action
// --------------------------------------------------------------------------
function initAttendanceQuickActions() {
  const forms = document.querySelectorAll(".attendance-action-form");
  forms.forEach(f => {
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(f);
      try {
        const res = await fetch("/api/attendance/quick", {
          method: "POST",
          body: formData,
        });
        const result = await res.json();
        if (result.success) {
          showToast(`Updated attendance for ${result.worker_name}`);
          setTimeout(() => location.reload(), 300);
        } else {
          showToast(result.error || "Update failed.");
        }
      } catch (err) {
        showToast("Error updating attendance.");
      }
    });
  });
}

// --------------------------------------------------------------------------
// 7. Toast Feedback
// --------------------------------------------------------------------------
function showToast(message) {
  const existing = document.querySelector(".toast-alert");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast-alert";
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.2s";
    setTimeout(() => toast.remove(), 250);
  }, 3000);
}

// --------------------------------------------------------------------------
// 8. Instant Client-Side Table Search / Filter
// --------------------------------------------------------------------------
function initTableFilter() {
  const searchInput = document.getElementById("tableSearchInput");
  if (!searchInput) return;

  searchInput.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase().trim();
    const rows = document.querySelectorAll(".filterable-table tbody tr");

    rows.forEach(row => {
      // Don't hide empty state rows
      if (row.querySelector(".empty-state")) return;
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(query) ? "" : "none";
    });
  });
}

// --------------------------------------------------------------------------
// 9. Worker Deletion Safeguard
// --------------------------------------------------------------------------
function initWorkerDeleteHandler() {
  const deleteModal = document.getElementById("delete-worker-modal");
  const deleteForm = document.getElementById("delete-worker-form");
  const nameText = document.getElementById("delete-worker-name-text");
  const codeText = document.getElementById("delete-worker-code-text");
  const cancelBtn = document.getElementById("btn-cancel-delete");
  const closeBtn = document.getElementById("btn-close-delete-modal");

  if (!deleteModal) return;

  const closeModal = () => {
    deleteModal.style.display = "none";
  };

  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  deleteModal.addEventListener("click", (e) => {
    if (e.target === deleteModal) closeModal();
  });

  document.querySelectorAll(".btn-delete-worker").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const workerId = btn.dataset.workerId;
      const workerName = btn.dataset.workerName || "Worker";
      const workerCode = btn.dataset.workerCode || "";

      if (nameText) nameText.textContent = workerName;
      if (codeText) codeText.textContent = workerCode;
      if (deleteForm) deleteForm.action = `/workers/${workerId}/delete`;

      deleteModal.style.display = "flex";
    });
  });
}

// --------------------------------------------------------------------------
// 10. Printable QR Badge Generator Modal
// --------------------------------------------------------------------------
function initQrBadgeModal() {
  const qrModal = document.getElementById("qr-badge-modal");
  const closeBtn = document.getElementById("btn-close-qr-modal");
  const dismissBtn = document.getElementById("btn-dismiss-qr-modal");
  const printBtn = document.getElementById("btn-print-badge");
  const qrContainer = document.getElementById("modal-qr-container");

  const nameEl = document.getElementById("badge-worker-name");
  const codeEl = document.getElementById("badge-worker-code");
  const deptEl = document.getElementById("badge-worker-dept");
  const zoneEl = document.getElementById("badge-worker-zone");
  const avatarEl = document.getElementById("badge-avatar-initials");

  if (!qrModal) return;

  const closeModal = () => {
    qrModal.style.display = "none";
  };

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (dismissBtn) dismissBtn.addEventListener("click", closeModal);
  qrModal.addEventListener("click", (e) => {
    if (e.target === qrModal) closeModal();
  });

  if (printBtn) {
    printBtn.addEventListener("click", () => {
      window.print();
    });
  }

  document.querySelectorAll(".btn-qr-badge").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const workerName = btn.dataset.workerName || "Worker";
      const workerCode = btn.dataset.workerCode || "EMP-000";
      const workerDept = btn.dataset.workerDept || "Operations";
      const workerZone = btn.dataset.workerZone || "Plant Floor";

      if (nameEl) nameEl.textContent = workerName;
      if (codeEl) codeEl.textContent = workerCode;
      if (deptEl) deptEl.textContent = workerDept;
      if (zoneEl) zoneEl.textContent = workerZone;
      if (avatarEl) avatarEl.textContent = workerName.substring(0, 2).toUpperCase();

      // Render crisp QR code using local qrcode.min.js
      if (qrContainer && typeof QRCode !== "undefined") {
        qrContainer.innerHTML = "";
        try {
          new QRCode(qrContainer, {
            text: workerCode,
            width: 140,
            height: 140,
            colorDark: "#0f172a",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.H,
          });
        } catch (qrErr) {
          console.error("QRCode rendering error:", qrErr);
          qrContainer.innerHTML = `<code style="font-size:12px; font-weight:700;">${workerCode}</code>`;
        }
      }

      qrModal.style.display = "flex";
    });
  });
}

// --------------------------------------------------------------------------
// 11. Real-time QR Attendance Scanner Kiosk
// --------------------------------------------------------------------------
let html5QrScannerInstance = null;
let isQrScanning = false;
let qrScanCooldown = false;

function initQrAttendanceScanner() {
  const kioskPanel = document.getElementById("qr-kiosk-panel");
  const toggleBtn = document.getElementById("btn-toggle-qr-kiosk");
  const closeBtn = document.getElementById("btn-close-qr-kiosk");
  const manualTestBtn = document.getElementById("btn-manual-qr-test");
  const manualTestInput = document.getElementById("manual-qr-test-input");

  if (!kioskPanel) return;

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      if (kioskPanel.style.display === "none" || !kioskPanel.style.display) {
        openQrKiosk();
      } else {
        closeQrKiosk();
      }
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", closeQrKiosk);
  }

  if (manualTestBtn && manualTestInput) {
    manualTestBtn.addEventListener("click", () => {
      const code = manualTestInput.value.trim();
      if (!code) {
        showToast("Please enter an employee code to test.");
        return;
      }
      processAttendanceQrCode(code);
    });

    manualTestInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        manualTestBtn.click();
      }
    });
  }
}

async function openQrKiosk() {
  const kioskPanel = document.getElementById("qr-kiosk-panel");
  const statusBadge = document.getElementById("qr-kiosk-status");
  if (!kioskPanel) return;

  kioskPanel.style.display = "block";
  if (statusBadge) {
    statusBadge.innerHTML = `<span class="pulse-dot"></span> Camera Initializing...`;
  }

  if (typeof Html5Qrcode === "undefined") {
    showToast("QR Scanner engine is initializing...");
    return;
  }

  try {
    if (!html5QrScannerInstance) {
      html5QrScannerInstance = new Html5Qrcode("qr-reader");
    }

    const config = {
      fps: 10,
      qrbox: { width: 220, height: 220 },
      aspectRatio: 1.0,
    };

    await html5QrScannerInstance.start(
      { facingMode: "environment" },
      config,
      (decodedText) => {
        if (qrScanCooldown) return;
        qrScanCooldown = true;
        processAttendanceQrCode(decodedText);
        setTimeout(() => { qrScanCooldown = false; }, 2500);
      },
      () => {}
    );

    isQrScanning = true;
    if (statusBadge) {
      statusBadge.innerHTML = `<span class="pulse-dot"></span> Active — Waiting for Badge`;
    }
  } catch (err) {
    console.warn("Html5Qrcode environment start failed, attempting fallback:", err);
    try {
      // Fallback without environment constraint
      await html5QrScannerInstance.start(
        true,
        { fps: 10, qrbox: { width: 220, height: 220 } },
        (decodedText) => {
          if (qrScanCooldown) return;
          qrScanCooldown = true;
          processAttendanceQrCode(decodedText);
          setTimeout(() => { qrScanCooldown = false; }, 2500);
        },
        () => {}
      );
      isQrScanning = true;
      if (statusBadge) {
        statusBadge.innerHTML = `<span class="pulse-dot"></span> Active — Waiting for Badge`;
      }
    } catch (fallbackErr) {
      console.error("QR scanner start failed:", fallbackErr);
      if (statusBadge) {
        statusBadge.className = "pill-badge pill-neutral";
        statusBadge.textContent = "Camera Unavailable";
      }
      showToast("Could not access camera for QR scanner. You can use manual code check-in.");
    }
  }
}

async function closeQrKiosk() {
  const kioskPanel = document.getElementById("qr-kiosk-panel");
  if (kioskPanel) kioskPanel.style.display = "none";

  if (html5QrScannerInstance && isQrScanning) {
    try {
      await html5QrScannerInstance.stop();
    } catch (e) {
      console.warn("Error stopping QR scanner:", e);
    }
    isQrScanning = false;
  }
}

async function processAttendanceQrCode(qrData) {
  const successCard = document.getElementById("qr-scan-success-card");
  const idleGuide = document.getElementById("qr-idle-guide");
  const fbAction = document.getElementById("qr-feedback-action");
  const fbName = document.getElementById("qr-feedback-name");
  const fbCode = document.getElementById("qr-feedback-code");
  const fbTime = document.getElementById("qr-feedback-time");
  const fbDept = document.getElementById("qr-feedback-dept");

  try {
    const res = await fetch("/api/attendance/qr-scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_data: qrData }),
    });

    const data = await res.json();

    if (data.success) {
      const w = data.worker;
      if (fbAction) fbAction.textContent = data.action === "check_in" ? "CHECK-IN RECORDED" : "CHECK-OUT RECORDED";
      if (fbName) fbName.textContent = w.full_name;
      if (fbCode) fbCode.textContent = w.employee_code;
      if (fbTime) fbTime.textContent = data.timestamp;
      if (fbDept) fbDept.textContent = w.department;

      if (successCard) successCard.style.display = "flex";
      if (idleGuide) idleGuide.style.display = "none";

      showToast(`✓ ${w.full_name} registered (${data.timestamp})`);

      // Update table row live
      updateAttendanceTableRow(w.id, data.status, data.timestamp, data.action);

      // Play soft audio beep
      playScanBeep();

      // Reset card after 4 seconds
      setTimeout(() => {
        if (successCard) successCard.style.display = "none";
        if (idleGuide) idleGuide.style.display = "block";
      }, 4000);
    } else {
      showToast(`QR Scan: ${data.error || "Worker not found"}`);
    }
  } catch (netErr) {
    showToast("Network error submitting QR scan.");
  }
}

function updateAttendanceTableRow(workerId, status, timestamp, action) {
  const row = document.getElementById(`attendance-row-${workerId}`);
  if (!row) return;

  const colStatus = row.querySelector(".col-status");
  const colCheckin = row.querySelector(".col-checkin");
  const colCheckout = row.querySelector(".col-checkout");

  if (colStatus) {
    if (status === "present") {
      colStatus.innerHTML = `<span class="badge badge-safe"><span class="badge-dot"></span> On Duty</span>`;
    } else if (status === "absent") {
      colStatus.innerHTML = `<span class="badge badge-high"><span class="badge-dot"></span> Absent</span>`;
    }
  }

  if (action === "check_in" && colCheckin) {
    colCheckin.innerHTML = `<span style="font-size: 13px; font-weight: 600; color: var(--safe-fg);">${timestamp}</span>`;
  } else if (action === "check_out" && colCheckout) {
    colCheckout.innerHTML = `<span style="font-size: 13px; font-weight: 600;">${timestamp}</span>`;
  }
}

function playScanBeep() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.15);
  } catch (e) {
    // Non-fatal if audio context not permitted
  }
}


