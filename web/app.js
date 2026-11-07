// ==========================================================================
// THE EXTRACTOR — V2.7.0 CLIENT SCRIPT (BATCH, HISTORY & FORMATS)
// ==========================================================================


const API_BASE = "";

// State
let apiKey = sessionStorage.getItem("extractor_api_key") || "";
let currentVideoData = null;
let activeTaskId = null;
let pollTimer = null;
let activeTasksMap = new Map();
let batchPollTimer = null;

function authHeaders() {
  const headers = {};
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

function setApiKey(key) {
  apiKey = key ? key.trim() : "";
  if (apiKey) {
    sessionStorage.setItem("extractor_api_key", apiKey);
  } else {
    sessionStorage.removeItem("extractor_api_key");
  }
}

// Tab Elements
const tabSingle = document.getElementById("tabSingle");
const tabBatch = document.getElementById("tabBatch");
const singleInputCard = document.getElementById("singleInputCard");
const batchInputCard = document.getElementById("batchInputCard");

// Single Mode Elements
const ytUrlInput = document.getElementById("ytUrlInput");
const pasteBtn = document.getElementById("pasteBtn");
const inspectBtn = document.getElementById("inspectBtn");
const inspectLoader = document.getElementById("inspectLoader");
const loaderStatusText = document.getElementById("loaderStatusText");
const errorBanner = document.getElementById("errorBanner");
const errorMessage = document.getElementById("errorMessage");
const resultSection = document.getElementById("resultSection");

// Batch Elements
const batchUrlsInput = document.getElementById("batchUrlsInput");
const batchPasteBtn = document.getElementById("batchPasteBtn");
const startBatchBtn = document.getElementById("startBatchBtn");
const batchCount = document.getElementById("batchCount");
const batchQueueSection = document.getElementById("batchQueueSection");
const queueList = document.getElementById("queueList");
const clearQueueBtn = document.getElementById("clearQueueBtn");
const cancelAllBtn = document.getElementById("cancelAllBtn");
const queueSummaryText = document.getElementById("queueSummaryText");
const cntQueued = document.getElementById("cntQueued");
const cntRunning = document.getElementById("cntRunning");
const cntCompleted = document.getElementById("cntCompleted");
const cntFailed = document.getElementById("cntFailed");


// Preview Elements
const videoThumb = document.getElementById("videoThumb");
const videoDuration = document.getElementById("videoDuration");
const videoTitle = document.getElementById("videoTitle");
const videoChannel = document.getElementById("videoChannel");
const videoViews = document.getElementById("videoViews");
const videoDate = document.getElementById("videoDate");
const videoDesc = document.getElementById("videoDesc");
const tagsContainer = document.getElementById("tagsContainer");
const tagsCount = document.getElementById("tagsCount");
const transcriptContainer = document.getElementById("transcriptContainer");
const transcriptSearchInput = document.getElementById("transcriptSearchInput");
const tabTranscript = document.getElementById("tabTranscript");
const tabDescription = document.getElementById("tabDescription");
const tabComments = document.getElementById("tabComments");
const tabTags = document.getElementById("tabTags");
const paneTranscript = document.getElementById("paneTranscript");
const paneDescription = document.getElementById("paneDescription");
const paneComments = document.getElementById("paneComments");
const paneTags = document.getElementById("paneTags");
const commentSearchInput = document.getElementById("commentSearchInput");
const loadCommentsBtn = document.getElementById("loadCommentsBtn");
const commentsContainer = document.getElementById("commentsContainer");
const tagsCountBadge = document.getElementById("tagsCountBadge");

// Video Player & Visual Trimmer Elements
const videoContainer = document.getElementById("videoContainer");
const thumbWrapper = document.getElementById("thumbWrapper");
const playPreviewBtn = document.getElementById("playPreviewBtn");
const playerFrameWrapper = document.getElementById("playerFrameWrapper");
const videoPlayerFrame = document.getElementById("videoPlayerFrame");
const closePlayerBtn = document.getElementById("closePlayerBtn");

const toggleTrimmerBtn = document.getElementById("toggleTrimmerBtn");
const trimmerControls = document.getElementById("trimmerControls");
const trimStartLabel = document.getElementById("trimStartLabel");
const trimDurationLabel = document.getElementById("trimDurationLabel");
const trimEndLabel = document.getElementById("trimEndLabel");
const rangeHighlight = document.getElementById("rangeHighlight");
const rangeStart = document.getElementById("rangeStart");
const rangeEnd = document.getElementById("rangeEnd");
const snippetStart = document.getElementById("snippetStart");
const snippetEnd = document.getElementById("snippetEnd");
const resetSnippetBtn = document.getElementById("resetSnippetBtn");
const customFolderInput = document.getElementById("customFolderInput");
const browseFolderBtn = document.getElementById("browseFolderBtn");

let isTrimmerEnabled = false;
let currentComments = [];
let totalDurationSeconds = 0;

// Customization & Options
const selResolution = document.getElementById("selResolution");
const selAudio = document.getElementById("selAudio");
const optVideo = document.getElementById("optVideo");
const optAudio = document.getElementById("optAudio");
const optDoc = document.getElementById("optDoc");
const optJson = document.getElementById("optJson");
const downloadBtn = document.getElementById("downloadBtn");
const selectAllBtn = document.getElementById("selectAllBtn");
const selectOnlyAudioBtn = document.getElementById("selectOnlyAudioBtn");
const selectOnlyVideoBtn = document.getElementById("selectOnlyVideoBtn");


// Progress Elements
const progressCard = document.getElementById("progressCard");
const progressBar = document.getElementById("progressBar");
const progressPercent = document.getElementById("progressPercent");
const progressPhaseText = document.getElementById("progressPhaseText");
const progressSpeed = document.getElementById("progressSpeed");
const progressEta = document.getElementById("progressEta");
const finishedActions = document.getElementById("finishedActions");

// History & Settings Modals
const navHistoryBtn = document.getElementById("navHistoryBtn");
const historyCountBadge = document.getElementById("historyCountBadge");
const historyModal = document.getElementById("historyModal");
const closeHistoryBtn = document.getElementById("closeHistoryBtn");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");
const historyListContainer = document.getElementById("historyListContainer");
const historySearchInput = document.getElementById("historySearchInput");
const clearSearchBtn = document.getElementById("clearSearchBtn");

const navSettingsBtn = document.getElementById("navSettingsBtn");
const settingsModal = document.getElementById("settingsModal");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const settingsContent = document.getElementById("settingsContent");

// Disk & Update Alerts
const diskBadge = document.getElementById("diskBadge");
const diskUsageText = document.getElementById("diskUsageText");
const ytdlpAlertBanner = document.getElementById("ytdlpAlertBanner");
const ytdlpCurrentVer = document.getElementById("ytdlpCurrentVer");
const ytdlpLatestVer = document.getElementById("ytdlpLatestVer");
const dismissYtdlpAlert = document.getElementById("dismissYtdlpAlert");
const jsAlertBanner = document.getElementById("jsAlertBanner");
const dismissJsAlert = document.getElementById("dismissJsAlert");
const ffmpegAlertBanner = document.getElementById("ffmpegAlertBanner");
const dismissFfmpegAlert = document.getElementById("dismissFfmpegAlert");

// Theme Toggle Elements
const themeToggleBtn = document.getElementById("themeToggleBtn");
const themeIcon = document.getElementById("themeIcon");
const themeLabel = document.getElementById("themeLabel");

// Modern Description Elements
const videoDescWrapper = document.getElementById("videoDescWrapper");
const descLineCount = document.getElementById("descLineCount");
const toggleDescSearchBtn = document.getElementById("toggleDescSearchBtn");
const toggleDescExpandBtn = document.getElementById("toggleDescExpandBtn");
const descSearchRow = document.getElementById("descSearchRow");
const descSearchInput = document.getElementById("descSearchInput");
const descSearchMatchCount = document.getElementById("descSearchMatchCount");

// Quick Actions
const openFolderBtn = document.getElementById("openFolderBtn");
const openFolderActionBtn = document.getElementById("openFolderActionBtn");
const openAudacityBtn = document.getElementById("openAudacityBtn");
const openAudacityActionBtn = document.getElementById("openAudacityActionBtn");
const refreshCommentsBtn = document.getElementById("refreshCommentsBtn");
const copyTagsBtn = document.getElementById("copyTagsBtn");
const copyTranscriptBtn = document.getElementById("copyTranscriptBtn");
const copyDescBtn = document.getElementById("copyDescBtn");
const toast = document.getElementById("toast");


// Toast Utility
function showToast(msg) {
  toast.textContent = msg;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 2500);
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.classList.remove("hidden");
  inspectLoader.classList.add("hidden");
}

function clearError() {
  errorBanner.classList.add("hidden");
}

// 1. Tab Navigation & Input Caching Engine
function saveInputCache() {
  try {
    if (ytUrlInput) sessionStorage.setItem("extractor_cached_single_url", ytUrlInput.value);
    if (batchUrlsInput) sessionStorage.setItem("extractor_cached_batch_urls", batchUrlsInput.value);
    if (customFolderInput) localStorage.setItem("extractor_cached_folder", customFolderInput.value);
  } catch (e) {
    /* ignore storage errors */
  }
}

function restoreInputCache() {
  try {
    const cachedSingle = sessionStorage.getItem("extractor_cached_single_url");
    if (cachedSingle && ytUrlInput && !ytUrlInput.value) {
      ytUrlInput.value = cachedSingle;
    }

    const cachedBatch = sessionStorage.getItem("extractor_cached_batch_urls");
    if (cachedBatch && batchUrlsInput && !batchUrlsInput.value) {
      batchUrlsInput.value = cachedBatch;
      updateBatchCount();
    }

    const cachedFolder = localStorage.getItem("extractor_cached_folder");
    if (cachedFolder && customFolderInput && !customFolderInput.value) {
      customFolderInput.value = cachedFolder;
    }

    const activeTab = sessionStorage.getItem("extractor_active_tab");
    if (activeTab === "batch") {
      switchToBatchTab();
    }
  } catch (e) {
    /* ignore storage errors */
  }
}

function switchToSingleTab() {
  tabSingle.classList.add("active");
  tabBatch.classList.remove("active");
  singleInputCard.classList.remove("hidden");
  batchInputCard.classList.add("hidden");
  if (currentVideoData) {
    resultSection.classList.remove("hidden");
  }
  sessionStorage.setItem("extractor_active_tab", "single");
}

function switchToBatchTab() {
  tabBatch.classList.add("active");
  tabSingle.classList.remove("active");
  batchInputCard.classList.remove("hidden");
  singleInputCard.classList.add("hidden");
  resultSection.classList.add("hidden");
  sessionStorage.setItem("extractor_active_tab", "batch");
}

tabSingle.addEventListener("click", switchToSingleTab);
tabBatch.addEventListener("click", switchToBatchTab);

if (ytUrlInput) {
  ytUrlInput.addEventListener("input", saveInputCache);
}
if (batchUrlsInput) {
  batchUrlsInput.addEventListener("input", () => {
    updateBatchCount();
    saveInputCache();
  });
}
if (customFolderInput) {
  customFolderInput.addEventListener("input", saveInputCache);
}

// Native Folder Browser Handler
if (browseFolderBtn) {
  browseFolderBtn.addEventListener("click", async () => {
    // 1. Try modern browser File System Access API
    if (window.showDirectoryPicker) {
      try {
        const handle = await window.showDirectoryPicker();
        if (handle && handle.name) {
          if (customFolderInput) {
            customFolderInput.value = handle.name;
            saveInputCache();
            showToast(`Selected folder: ${handle.name}`);
          }
          return;
        }
      } catch (err) {
        if (err.name === "AbortError") return; // User cancelled
        // Fall back to server host dialog
      }
    }

    // 2. Fall back to backend host OS folder dialog
    try {
      showToast("Opening folder browser...");
      const res = await fetch(`${API_BASE}/api/browse-folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.folder) {
          if (customFolderInput) {
            customFolderInput.value = data.folder;
            saveInputCache();
            showToast(`Selected folder: ${data.folder}`);
          }
        }
      } else {
        showToast("Browse folder requires direct server access");
      }
    } catch (e) {
      showToast("Folder browser unavailable");
    }
  });
}

// 2. Single Video Paste & Input
pasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      ytUrlInput.value = text.trim();
      saveInputCache();
      inspectVideo();
    }
  } catch (err) {
    ytUrlInput.focus();
    showToast("Please press Ctrl+V to paste URL");
  }
});

ytUrlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") inspectVideo();
});

inspectBtn.addEventListener("click", () => inspectVideo());

// 3. Batch Input Handlers
batchPasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      batchUrlsInput.value = text.trim();
      updateBatchCount();
      saveInputCache();
    }
  } catch (err) {
    batchUrlsInput.focus();
  }
});

function updateBatchCount() {
  const urls = getBatchUrls();
  batchCount.textContent = urls.length;
}

function getBatchUrls() {
  const raw = batchUrlsInput.value.trim();
  if (!raw) return [];
  return raw
    .split(/[\n,]+/)
    .map((u) => u.trim())
    .filter((u) => /^https?:\/\//i.test(u));
}

startBatchBtn.addEventListener("click", async () => {
  const urls = getBatchUrls();
  if (!urls.length) {
    showToast("Please enter at least one valid URL (http:// or https://)");
    return;
  }

  const [audioCodec, audioBitrate] = selAudio.value.split("-");
  const payload = {
    urls: urls,
    download_video: optVideo.checked,
    download_audio: optAudio.checked,
    download_doc: optDoc.checked,
    video_resolution: selResolution.value,
    audio_format: audioCodec,
    audio_bitrate: audioBitrate,
  };

  try {
    startBatchBtn.disabled = true;
    startBatchBtn.textContent = "Queueing...";
    const res = await fetch(`${API_BASE}/api/batch-download`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to start batch");

    showToast(`Queued ${data.total} item(s)!`);
    if (data.skipped && data.skipped.length > 0) {
      showToast(`Warning: ${data.skipped.length} playlist(s) could not be expanded`);
    }
    batchQueueSection.classList.remove("hidden");

    data.tasks.forEach((t) => {
      activeTasksMap.set(t.task_id, {
        task_id: t.task_id,
        url: t.url,
        status: "queued",
        percent: "0%",
      });
    });

    renderQueue();
    startBatchPolling();
    batchUrlsInput.value = "";
    updateBatchCount();
  } catch (err) {
    showError(err.message);
  } finally {
    startBatchBtn.disabled = false;
    startBatchBtn.textContent = `Queue Batch Download (${getBatchUrls().length} items)`;
  }
});

function renderQueue() {
  queueList.innerHTML = "";
  let qCnt = 0, rCnt = 0, cCnt = 0, fCnt = 0;

  activeTasksMap.forEach((task) => {
    if (task.status === "queued") qCnt++;
    else if (task.status === "running") rCnt++;
    else if (task.status === "completed") cCnt++;
    else if (task.status === "error" || task.status === "cancelled") fCnt++;

    const item = document.createElement("div");
    item.className = "queue-item";
    const displayStatus =
      task.status === "queued" ? "queued" : task.status;
    const badgeClass =
      task.status === "queued" ? "status-waiting" : `status-${task.status}`;

    const canCancel = task.status === "queued" || task.status === "running";
    const cancelBtnHtml = canCancel
      ? `<button class="btn btn-ghost btn-sm" style="color: #ef4444; margin-left: 8px;" onclick="cancelTask('${task.task_id}')">Cancel</button>`
      : "";

    item.innerHTML = `
      <div class="queue-info">
        <span class="queue-url">${escapeHtml(task.url)}</span>
        <span class="queue-status-text">${escapeHtml(task.message || task.percent || "")}</span>
      </div>
      <div style="display: flex; align-items: center;">
        <span class="queue-status-badge ${badgeClass}">${displayStatus}</span>
        ${cancelBtnHtml}
      </div>
    `;
    queueList.appendChild(item);
  });

  if (cntQueued) cntQueued.textContent = qCnt;
  if (cntRunning) cntRunning.textContent = rCnt;
  if (cntCompleted) cntCompleted.textContent = cCnt;
  if (cntFailed) cntFailed.textContent = fCnt;
  if (queueSummaryText) queueSummaryText.textContent = `${activeTasksMap.size} items`;
}

window.cancelTask = async function(taskId) {
  try {
    const res = await fetch(`${API_BASE}/api/tasks/${taskId}/cancel`, {
      method: "POST",
      headers: { ...authHeaders() },
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Server rejected cancellation");
    }
    const t = activeTasksMap.get(taskId);
    if (t) {
      t.status = "cancelled";
      t.message = "Cancelled by user";
      renderQueue();
    }
    showToast("Task cancelled");
  } catch (e) {
    showToast(`Failed to cancel task: ${e.message}`);
  }
};

if (cancelAllBtn) {
  cancelAllBtn.addEventListener("click", async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tasks/cancel-all`, {
        method: "POST",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Server rejected cancellation");
      }
      activeTasksMap.forEach((t) => {
        if (t.status === "queued" || t.status === "running") {
          t.status = "cancelled";
          t.message = "Cancelled by user";
        }
      });
      renderQueue();
      showToast("All active downloads cancelled");
    } catch (e) {
      showToast(`Failed to cancel downloads: ${e.message}`);
    }
  });
}


function startBatchPolling() {
  if (batchPollTimer) return;
  batchPollTimer = setInterval(async () => {
    try {
      // Use single bulk progress endpoint (EXT-004)
      const res = await fetch(`${API_BASE}/api/progress`, {
        headers: { ...authHeaders() },
      });
      if (res.ok) {
        const data = await res.json();
        (data.tasks || []).forEach((t) => {
          if (activeTasksMap.has(t.task_id)) {
            activeTasksMap.set(t.task_id, { ...activeTasksMap.get(t.task_id), ...t });
          }
        });
      }
    } catch (e) {}

    renderQueue();

    let allFinished = true;
    for (const task of activeTasksMap.values()) {
      if (task.status === "queued" || task.status === "running") {
        allFinished = false;
        break;
      }
    }

    if (allFinished) {
      clearInterval(batchPollTimer);
      batchPollTimer = null;
      loadHistory();
      showToast("Batch processing finished!");
    }
  }, 1000);
}

clearQueueBtn.addEventListener("click", () => {
  for (const [id, t] of activeTasksMap.entries()) {
    if (t.status === "completed" || t.status === "error" || t.status === "cancelled") {
      activeTasksMap.delete(id);
    }
  }
  renderQueue();
  if (activeTasksMap.size === 0) batchQueueSection.classList.add("hidden");
});

// 4. Single Video Inspection
async function inspectVideo() {
  const url = ytUrlInput.value.trim();
  if (!url) {
    showToast("Please enter a YouTube URL");
    return;
  }

  clearError();
  resultSection.classList.add("hidden");
  inspectLoader.classList.remove("hidden");
  loaderStatusText.textContent = "Analyzing metadata, tags, and transcript...";

  try {
    const res = await fetch(`${API_BASE}/api/inspect`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ url }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Inspection failed");

    if (data.is_playlist) {
      showToast(`Playlist detected: ${data.playlist_count} videos! Switching to batch tab.`);
      tabBatch.click();
      batchUrlsInput.value = data.items.map((i) => i.url).join("\n");
      updateBatchCount();
      return;
    }

    currentVideoData = data.data;
    renderVideoWorkspace(currentVideoData);
    resultSection.classList.remove("hidden");
    resultSection.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    showError(err.message);
  } finally {
    // Guaranteed loader cleanup (EXT-018)
    inspectLoader.classList.add("hidden");
  }
}


// ---------------------------------------------------------------------------
// Helpers: Time Formatting & Parsing
// ---------------------------------------------------------------------------

function formatSecondsToTime(sec) {
  if (isNaN(sec) || sec < 0) return "0:00";
  const total = Math.floor(sec);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

function parseTimeToSeconds(val) {
  if (!val) return null;
  const s = String(val).trim().replace(/s$/i, "");
  if (!s) return null;
  if (s.includes(":")) {
    const parts = s.split(":").map((p) => parseFloat(p.trim()));
    if (parts.some(isNaN)) return null;
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }
  const num = parseFloat(s);
  return isNaN(num) ? null : num;
}

// ---------------------------------------------------------------------------
// Video Player Controls
// ---------------------------------------------------------------------------

if (playPreviewBtn) {
  playPreviewBtn.addEventListener("click", () => {
    if (!currentVideoData || !currentVideoData.id) return;
    // Standard embed URL with autoplay and origin parameters
    const embedUrl = `https://www.youtube.com/embed/${currentVideoData.id}?autoplay=1&rel=0&enablejsapi=1`;
    videoPlayerFrame.src = embedUrl;
    playerFrameWrapper.classList.remove("hidden");
    thumbWrapper.classList.add("hidden");
  });
}

if (closePlayerBtn) {
  closePlayerBtn.addEventListener("click", () => {
    videoPlayerFrame.src = "";
    playerFrameWrapper.classList.add("hidden");
    thumbWrapper.classList.remove("hidden");
  });
}

// ---------------------------------------------------------------------------
// Visual Video Trimming & Timeline Cutter
// ---------------------------------------------------------------------------

function updateTrimmerUI() {
  if (!totalDurationSeconds || totalDurationSeconds <= 0) return;
  const sVal = parseFloat(rangeStart.value);
  const eVal = parseFloat(rangeEnd.value);

  // Prevent start crossing end
  const actualStart = Math.min(sVal, eVal);
  const actualEnd = Math.max(sVal, eVal);

  const startSec = (actualStart / 100) * totalDurationSeconds;
  const endSec = (actualEnd / 100) * totalDurationSeconds;
  const clipLen = endSec - startSec;

  trimStartLabel.textContent = `Start: ${formatSecondsToTime(startSec)}`;
  trimEndLabel.textContent = `End: ${formatSecondsToTime(endSec)}`;
  trimDurationLabel.textContent = `Clip: ${formatSecondsToTime(clipLen)} (${Math.round(clipLen)}s)`;

  // Update text inputs
  snippetStart.value = formatSecondsToTime(startSec);
  snippetEnd.value = formatSecondsToTime(endSec);

  // Position highlight bar
  rangeHighlight.style.left = `${actualStart}%`;
  rangeHighlight.style.width = `${actualEnd - actualStart}%`;
}

if (rangeStart && rangeEnd) {
  rangeStart.addEventListener("input", () => {
    if (parseFloat(rangeStart.value) > parseFloat(rangeEnd.value) - 1) {
      rangeStart.value = parseFloat(rangeEnd.value) - 1;
    }
    updateTrimmerUI();
  });

  rangeEnd.addEventListener("input", () => {
    if (parseFloat(rangeEnd.value) < parseFloat(rangeStart.value) + 1) {
      rangeEnd.value = parseFloat(rangeStart.value) + 1;
    }
    updateTrimmerUI();
  });
}

if (snippetStart) {
  snippetStart.addEventListener("change", () => {
    const s = parseTimeToSeconds(snippetStart.value);
    if (s !== null && totalDurationSeconds > 0) {
      const pct = Math.min(100, Math.max(0, (s / totalDurationSeconds) * 100));
      rangeStart.value = pct;
      updateTrimmerUI();
    }
  });
}

if (snippetEnd) {
  snippetEnd.addEventListener("change", () => {
    const e = parseTimeToSeconds(snippetEnd.value);
    if (e !== null && totalDurationSeconds > 0) {
      const pct = Math.min(100, Math.max(0, (e / totalDurationSeconds) * 100));
      rangeEnd.value = pct;
      updateTrimmerUI();
    }
  });
}

if (toggleTrimmerBtn) {
  toggleTrimmerBtn.addEventListener("click", () => {
    isTrimmerEnabled = !isTrimmerEnabled;
    if (isTrimmerEnabled) {
      trimmerControls.classList.remove("hidden");
      toggleTrimmerBtn.textContent = "✕ Disable Trimmer";
      toggleTrimmerBtn.classList.add("btn-secondary");
      updateTrimmerUI();
    } else {
      trimmerControls.classList.add("hidden");
      toggleTrimmerBtn.textContent = "✂️ Enable Trim Cut";
      toggleTrimmerBtn.classList.remove("btn-secondary");
      rangeStart.value = 0;
      rangeEnd.value = 100;
      snippetStart.value = "";
      snippetEnd.value = "";
    }
  });
}

if (resetSnippetBtn) {
  resetSnippetBtn.addEventListener("click", () => {
    rangeStart.value = 0;
    rangeEnd.value = 100;
    updateTrimmerUI();
    showToast("Reset to full video length");
  });
}

// ---------------------------------------------------------------------------
// Package Presets
// ---------------------------------------------------------------------------

if (selectAllBtn) {
  selectAllBtn.addEventListener("click", () => {
    optVideo.checked = true;
    optAudio.checked = true;
    optDoc.checked = true;
    if (optJson) optJson.checked = true;
    showToast("Selected all components");
  });
}

if (selectOnlyAudioBtn) {
  selectOnlyAudioBtn.addEventListener("click", () => {
    optVideo.checked = false;
    optAudio.checked = true;
    optDoc.checked = false;
    if (optJson) optJson.checked = false;
    showToast("Audio only selected");
  });
}

if (selectOnlyVideoBtn) {
  selectOnlyVideoBtn.addEventListener("click", () => {
    optVideo.checked = true;
    optAudio.checked = false;
    optDoc.checked = false;
    if (optJson) optJson.checked = false;
    showToast("Video only selected");
  });
}

// ---------------------------------------------------------------------------
// Sidebar Tabs & Transcripts / Comments / Tags
// ---------------------------------------------------------------------------

function switchSidebarTab(tabName) {
  [tabTranscript, tabDescription, tabComments, tabTags].forEach((btn) => btn && btn.classList.remove("active"));
  [paneTranscript, paneDescription, paneComments, paneTags].forEach((pane) => pane && pane.classList.add("hidden"));

  if (tabName === "transcript") {
    tabTranscript && tabTranscript.classList.add("active");
    paneTranscript && paneTranscript.classList.remove("hidden");
  } else if (tabName === "description") {
    tabDescription && tabDescription.classList.add("active");
    paneDescription && paneDescription.classList.remove("hidden");
  } else if (tabName === "comments") {
    tabComments && tabComments.classList.add("active");
    paneComments && paneComments.classList.remove("hidden");
  } else if (tabName === "tags") {
    tabTags && tabTags.classList.add("active");
    paneTags && paneTags.classList.remove("hidden");
  }
}

if (tabTranscript) tabTranscript.addEventListener("click", () => switchSidebarTab("transcript"));
if (tabDescription) tabDescription.addEventListener("click", () => switchSidebarTab("description"));
if (tabComments) tabComments.addEventListener("click", () => switchSidebarTab("comments"));
if (tabTags) tabTags.addEventListener("click", () => switchSidebarTab("tags"));

function renderTranscript(transcriptList) {
  transcriptContainer.innerHTML = "";
  const query = transcriptSearchInput ? transcriptSearchInput.value.trim().toLowerCase() : "";

  const filtered = query
    ? transcriptList.filter((t) => t.text.toLowerCase().includes(query))
    : transcriptList;

  if (filtered.length > 0) {
    filtered.forEach((t) => {
      const row = document.createElement("div");
      row.className = "transcript-item";
      let textContent = escapeHtml(t.text);
      if (query) {
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
        textContent = textContent.replace(regex, "<mark class='highlight'>$1</mark>");
      }
      row.innerHTML = `<span class="transcript-timestamp">[${t.timestamp}]</span> <span>${textContent}</span>`;
      transcriptContainer.appendChild(row);
    });
  } else {
    transcriptContainer.innerHTML = query
      ? `<p class='empty-text'>No matches found for "${escapeHtml(query)}".</p>`
      : "<p class='empty-text'>No spoken words or transcript detected.</p>";
  }
}

if (transcriptSearchInput) {
  transcriptSearchInput.addEventListener("input", () => {
    if (currentVideoData) {
      renderTranscript(currentVideoData.transcript || []);
    }
  });
}

// Comments Fetching & Filtering
async function fetchCommentsForVideo() {
  if (!currentVideoData || !currentVideoData.url) return;
  try {
    if (refreshCommentsBtn) {
      refreshCommentsBtn.disabled = true;
      refreshCommentsBtn.textContent = "⏳ Fetching...";
    }
    commentsContainer.innerHTML = `
      <div class="comments-empty-state">
        <span class="empty-icon">⏳</span>
        <p>Fetching top comments from YouTube...</p>
      </div>
    `;

    const res = await fetch(`${API_BASE}/api/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ url: currentVideoData.url, max_comments: 50 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not fetch comments");

    currentComments = data.comments || [];
    renderCommentsList();
  } catch (err) {
    commentsContainer.innerHTML = `<p class="empty-text">No comments retrieved or comments disabled by creator.</p>`;
  } finally {
    if (refreshCommentsBtn) {
      refreshCommentsBtn.disabled = false;
      refreshCommentsBtn.textContent = "🔄 Refresh";
    }
  }
}

if (refreshCommentsBtn) {
  refreshCommentsBtn.addEventListener("click", () => fetchCommentsForVideo());
}
if (loadCommentsBtn) {
  loadCommentsBtn.addEventListener("click", () => fetchCommentsForVideo());
}

function renderCommentsList() {
  commentsContainer.innerHTML = "";
  const query = commentSearchInput ? commentSearchInput.value.trim().toLowerCase() : "";

  const filtered = query
    ? currentComments.filter(
        (c) =>
          c.text.toLowerCase().includes(query) ||
          c.author.toLowerCase().includes(query)
      )
    : currentComments;

  if (filtered.length > 0) {
    filtered.forEach((c) => {
      const card = document.createElement("div");
      card.className = "comment-card";
      let textHtml = escapeHtml(c.text);
      if (query) {
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
        textHtml = textHtml.replace(regex, "<mark class='highlight'>$1</mark>");
      }

      card.innerHTML = `
        <div class="comment-head">
          <span class="comment-author">@${escapeHtml(c.author)}</span>
          ${c.like_count ? `<span class="comment-likes">👍 ${c.like_count}</span>` : ""}
        </div>
        <div class="comment-text">${textHtml}</div>
      `;
      commentsContainer.appendChild(card);
    });
  } else {
    commentsContainer.innerHTML = query
      ? `<p class='empty-text'>No comments matched "${escapeHtml(query)}".</p>`
      : "<p class='empty-text'>No comments loaded yet.</p>";
  }
}

if (commentSearchInput) {
  commentSearchInput.addEventListener("input", () => {
    if (currentComments && currentComments.length > 0) {
      renderCommentsList();
    }
  });
}

function renderVideoWorkspace(v) {
  videoThumb.src = v.thumbnail;
  videoDuration.textContent = v.duration_str;
  videoTitle.textContent = v.title;
  videoChannel.textContent = v.uploader;
  videoViews.textContent = Number(v.view_count).toLocaleString() + " views";
  videoDate.textContent = v.upload_date || "Unknown Date";
  renderDescription(v.description || "");

  // Reset Video Player
  videoPlayerFrame.src = "";
  playerFrameWrapper.classList.add("hidden");
  thumbWrapper.classList.remove("hidden");

  // Setup Trimmer bounds
  totalDurationSeconds = v.duration || 0;
  rangeStart.value = 0;
  rangeEnd.value = 100;
  snippetStart.value = "";
  snippetEnd.value = "";
  isTrimmerEnabled = false;
  trimmerControls.classList.add("hidden");
  toggleTrimmerBtn.textContent = "✂️ Enable Trim Cut";
  toggleTrimmerBtn.classList.remove("btn-secondary");

  if (totalDurationSeconds > 0) {
    trimStartLabel.textContent = "Start: 0:00";
    trimEndLabel.textContent = `End: ${formatSecondsToTime(totalDurationSeconds)}`;
    trimDurationLabel.textContent = "Clip: Full Video";
    rangeHighlight.style.left = "0%";
    rangeHighlight.style.width = "100%";
  }

  // Tags
  tagsContainer.innerHTML = "";
  const tagCount = v.tags ? v.tags.length : 0;
  tagsCount.textContent = tagCount;
  if (tagsCountBadge) tagsCountBadge.textContent = tagCount;

  if (v.tags && v.tags.length > 0) {
    v.tags.forEach((tag) => {
      const badge = document.createElement("span");
      badge.className = "tag-badge";
      badge.textContent = "#" + tag;
      tagsContainer.appendChild(badge);
    });
  } else {
    tagsContainer.innerHTML = "<span class='empty-text'>No hidden tags discovered.</span>";
  }

  // Transcript
  renderTranscript(v.transcript || []);

  // Comments (Always fetch/display automatically)
  if (v.comments && v.comments.length > 0) {
    currentComments = v.comments;
    renderCommentsList();
  } else {
    currentComments = [];
    fetchCommentsForVideo();
  }
  if (commentSearchInput) commentSearchInput.value = "";

  // Switch to transcript by default
  switchSidebarTab("transcript");

  // Reset Progress Card
  progressCard.classList.add("hidden");
  finishedActions.classList.add("hidden");
  progressBar.style.width = "0%";
}

// 5. Download Execution (Single)
downloadBtn.addEventListener("click", async () => {
  if (!currentVideoData) return;
  const hasAnySelection =
    optVideo.checked ||
    optAudio.checked ||
    optDoc.checked ||
    (optJson && optJson.checked);

  if (!hasAnySelection) {
    showToast("Please check at least one component (Video, Audio, Metadata, or JSON)!");
    return;
  }

  const [audioCodec, audioBitrate] = selAudio.value.split("-");

  // Snippet bounds
  let startTime = null;
  let endTime = null;
  if (isTrimmerEnabled) {
    if (snippetStart.value) {
      startTime = parseTimeToSeconds(snippetStart.value);
    }
    if (snippetEnd.value) {
      endTime = parseTimeToSeconds(snippetEnd.value);
    }
    if (startTime !== null && endTime !== null && startTime >= endTime) {
      showError("Snippet start time must be before end time!");
      return;
    }
  }

  const customDir = customFolderInput ? customFolderInput.value.trim() : null;

  const payload = {
    url: currentVideoData.url,
    download_video: optVideo.checked,
    download_audio: optAudio.checked,
    download_doc: optDoc.checked,
    download_json: optJson ? optJson.checked : false,
    video_resolution: selResolution.value,
    audio_format: audioCodec,
    audio_bitrate: audioBitrate,
    start_time: startTime,
    end_time: endTime,
    output_dir: customDir || null,
  };

  try {
    downloadBtn.disabled = true;
    const res = await fetch(`${API_BASE}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Download failed to start");

    activeTaskId = data.task_id;
    progressCard.classList.remove("hidden");
    finishedActions.classList.add("hidden");
    startProgressPolling(activeTaskId);
  } catch (err) {
    showError(err.message);
    downloadBtn.disabled = false;
  }
});


function startProgressPolling(taskId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/progress/${taskId}`, {
        headers: { ...authHeaders() },
      });
      if (!res.ok) return;

      const info = await res.json();
      progressBar.style.width = info.percent || "0%";
      progressPercent.textContent = info.percent || "0%";
      progressPhaseText.textContent = info.message || "Processing...";
      progressSpeed.textContent = info.speed ? `Speed: ${info.speed}` : "Speed: --";
      progressEta.textContent = info.eta ? `ETA: ${info.eta}` : "ETA: --";

      if (info.status === "completed") {
        clearInterval(pollTimer);
        pollTimer = null;
        downloadBtn.disabled = false;
        finishedActions.classList.remove("hidden");
        loadHistory();
      } else if (info.status === "cancelled") {
        clearInterval(pollTimer);
        pollTimer = null;
        downloadBtn.disabled = false;
        showToast(info.message || "Download was cancelled");
      } else if (info.status === "error" || info.status === "interrupted") {
        clearInterval(pollTimer);
        pollTimer = null;
        downloadBtn.disabled = false;
        showError(info.message || `Download ${info.status}`);
      }

    } catch (e) {
      console.error(e);
    }
  }, 500);
}

// 6. History Drawer Management
navHistoryBtn.addEventListener("click", () => {
  loadHistory();
  historyModal.classList.remove("hidden");
});
closeHistoryBtn.addEventListener("click", () => historyModal.classList.add("hidden"));

let historySearchTimer = null;
historySearchInput.addEventListener("input", () => {
  const query = historySearchInput.value.trim();
  if (query) {
    clearSearchBtn.classList.remove("hidden");
  } else {
    clearSearchBtn.classList.add("hidden");
  }
  clearTimeout(historySearchTimer);
  historySearchTimer = setTimeout(() => {
    loadHistory(query);
  }, 250);
});

clearSearchBtn.addEventListener("click", () => {
  historySearchInput.value = "";
  clearSearchBtn.classList.add("hidden");
  loadHistory();
});

async function loadHistory(searchQuery = null) {
  try {
    const url = new URL(`${window.location.origin}${API_BASE}/api/history`);
    if (searchQuery) {
      url.searchParams.set("search", searchQuery);
    }
    const res = await fetch(url.toString(), {
      headers: { ...authHeaders() },
    });
    if (!res.ok) return;
    const data = await res.json();
    const records = data.history || [];
    if (!searchQuery) {
      historyCountBadge.textContent = data.total !== undefined ? data.total : records.length;
    }

    if (!records.length) {
      historyListContainer.innerHTML = searchQuery
        ? `<p class='empty-state'>No matching records found for "${escapeHtml(searchQuery)}".</p>`
        : "<p class='empty-state'>No extraction history yet.</p>";
      return;
    }

    let html = `<table class="history-table">
      <thead>
        <tr>
          <th>Title / URL</th>
          <th>Channel</th>
          <th>Date</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>`;

    records.forEach((r) => {
      html += `
        <tr>
          <td><strong>${escapeHtml(r.title || r.url)}</strong></td>
          <td>${escapeHtml(r.channel || "--")}</td>
          <td>${r.created_at || "--"}</td>
          <td><span class="queue-status-badge status-${r.status}">${r.status}</span></td>
          <td>
            <button class="btn btn-ghost btn-sm text-danger" title="Delete record and downloaded files" onclick="deleteHistoryItem(${r.id}, true)">Delete</button>
          </td>
        </tr>`;
    });

    html += `</tbody></table>`;
    historyListContainer.innerHTML = html;
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

window.deleteHistoryItem = async function (id, deleteFiles = false) {
  try {
    await fetch(`${API_BASE}/api/history/${id}?delete_files=${deleteFiles}`, {
      method: "DELETE",
      headers: { ...authHeaders() },
    });
    loadHistory(historySearchInput.value.trim() || null);
    refreshSystemStatus();
  } catch (e) {
    showToast("Failed to delete record");
  }
};

clearHistoryBtn.addEventListener("click", async () => {
  const deleteFiles = confirm(
    "Delete history records AND their downloaded files from disk?\n\n(Click 'OK' to delete files + history, or 'Cancel' to keep files intact)"
  );
  try {
    await fetch(`${API_BASE}/api/history?delete_files=${deleteFiles}`, {
      method: "DELETE",
      headers: { ...authHeaders() },
    });
    loadHistory();
    refreshSystemStatus();
    showToast(deleteFiles ? "History and files deleted!" : "History cleared!");
  } catch (e) {
    showToast("Failed to clear history");
  }
});

// 7. System Status, Storage & Settings Drawer
async function refreshSystemStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/config`, {
      headers: { ...authHeaders() },
    });
    if (!res.ok) return;
    const cfg = await res.json();

    // 1. Disk usage indicator
    if (cfg.storage) {
      const mb = cfg.storage.total_mb;
      const count = cfg.storage.file_count;
      const freeGb = cfg.storage.disk_free_gb;
      diskUsageText.textContent = `${mb} MB (${count} files) • ${freeGb} GB Free`;

      if (cfg.storage.max_storage_gb > 0 && cfg.storage.total_gb >= cfg.storage.max_storage_gb * 0.85) {
        diskBadge.classList.add("disk-warn");
      } else {
        diskBadge.classList.remove("disk-warn");
      }
    }

    // 2. yt-dlp staleness check alert
    if (cfg.ytdlp && cfg.ytdlp.is_outdated) {
      ytdlpCurrentVer.textContent = cfg.ytdlp.installed;
      ytdlpLatestVer.textContent = cfg.ytdlp.latest;
      ytdlpAlertBanner.classList.remove("hidden");
    } else {
      ytdlpAlertBanner.classList.add("hidden");
    }

    // 3. JavaScript runtime missing alert
    if (cfg.js_runtime_available === false) {
      jsAlertBanner.classList.remove("hidden");
    } else {
      jsAlertBanner.classList.add("hidden");
    }

    // 4. FFmpeg missing alert
    if (cfg.ffmpeg_available === false) {
      ffmpegAlertBanner.classList.remove("hidden");
    } else {
      ffmpegAlertBanner.classList.add("hidden");
    }

    return cfg;
  } catch (e) {
    diskUsageText.textContent = "Disk: --";
  }
}

dismissYtdlpAlert.addEventListener("click", () => {
  ytdlpAlertBanner.classList.add("hidden");
});

dismissJsAlert.addEventListener("click", () => {
  jsAlertBanner.classList.add("hidden");
});

dismissFfmpegAlert.addEventListener("click", () => {
  ffmpegAlertBanner.classList.add("hidden");
});

navSettingsBtn.addEventListener("click", async () => {
  try {
    const cfg = await refreshSystemStatus();
    if (!cfg) throw new Error("Could not load config");

    const storage = cfg.storage || {};
    const ytdlp = cfg.ytdlp || {};

    settingsContent.innerHTML = `
      <div class="settings-grid" style="font-size: 0.88rem; line-height: 1.6;">
        <div class="settings-param-row">
          <span class="settings-label">Downloads Directory</span>
          <code class="settings-code">${escapeHtml(cfg.download_dir)}</code>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">Log File</span>
          <code class="settings-code">${escapeHtml(cfg.log_file || "extractor.log")}</code>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">Disk Storage</span>
          <span><code>${storage.total_mb || 0} MB</code> (${storage.file_count || 0} files) • Drive Free: <code>${storage.disk_free_gb || 0} GB</code></span>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">Retention Policy</span>
          <span>${storage.max_storage_gb > 0 ? `Max ${storage.max_storage_gb} GB` : "No size cap"} • ${storage.delete_after_days > 0 ? `Auto-purge > ${storage.delete_after_days} days` : "Never purge by age"}</span>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">yt-dlp Engine</span>
          <span><code>v${escapeHtml(ytdlp.installed || "unknown")}</code> ${ytdlp.is_outdated ? `<span class="status-chip chip-warn">Update available (${ytdlp.latest})</span>` : `<span class="status-chip chip-ok">Up to date</span>`}</span>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">JavaScript Runtime</span>
          <span>${cfg.js_runtime_available ? `<span class="status-chip chip-ok">Detected</span>` : `<span class="status-chip chip-warn">Not Found</span>`}</span>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">FFmpeg Suite</span>
          <span>${cfg.ffmpeg_available ? `<span class="status-chip chip-ok">Detected</span>` : `<span class="status-chip chip-warn">Not Found</span>`}</span>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">Audacity Binary</span>
          <span><code class="settings-code">${escapeHtml(cfg.audacity_path || "None")}</code> ${cfg.audacity_detected ? `<span class="status-chip chip-ok">Detected</span>` : `<span class="status-chip chip-muted">Not Found</span>`}</span>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">Cookies</span>
          <span>${cfg.has_cookies ? `<span class="status-chip chip-ok">Configured</span>` : `<span class="status-chip chip-muted">None</span>`}</span>
        </div>
        <div class="settings-param-row">
          <span class="settings-label">API Authentication</span>
          <span>${cfg.auth_enabled ? `<span class="status-chip chip-warn">Key Required</span>` : `<span class="status-chip chip-ok">Public / Local</span>`}</span>
        </div>

        <div class="settings-box">
          <div class="settings-box-info">
            <span class="settings-box-title">Storage Maintenance</span>
            <p class="settings-box-sub">Prune old downloads according to retention policy.</p>
          </div>
          <button id="runCleanupBtn" class="btn btn-ghost btn-sm">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px;">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            Run Cleanup Now
          </button>
        </div>

        <div class="settings-auth-box">
          <label class="settings-box-title" for="apiKeyInput">Client API Key (Header: X-API-Key)</label>
          <div style="display: flex; gap: 0.5rem; margin-top: 0.4rem;">
            <input 
              type="password" 
              id="apiKeyInput" 
              value="${escapeHtml(apiKey)}" 
              placeholder="Enter API Key if configured on server..." 
              class="settings-api-input"
            />
            <button id="saveApiKeyBtn" class="btn btn-primary btn-sm">Save Key</button>
          </div>
          <p class="settings-box-sub" style="margin-top: 0.35rem;">Stored securely in this browser session for authenticated API calls.</p>
        </div>
        <p style="margin-top: 1rem; font-size: 0.78rem; color: var(--text-muted);">Configuration can be permanently modified in <code>config.yaml</code>.</p>
      </div>
    `;

    document.getElementById("saveApiKeyBtn").addEventListener("click", () => {
      const keyVal = document.getElementById("apiKeyInput").value;
      setApiKey(keyVal);
      showToast("API Key saved for this session!");
      loadHistory();
      refreshSystemStatus();
    });

    document.getElementById("runCleanupBtn").addEventListener("click", async () => {
      try {
        const cRes = await fetch(`${API_BASE}/api/storage/cleanup`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({}),
        });
        const cData = await cRes.json();
        showToast(`Cleaned ${cData.deleted_files} file(s) (${cData.freed_mb} MB freed)!`);
        refreshSystemStatus();
      } catch (e) {
        showToast("Storage cleanup failed");
      }
    });

    settingsModal.classList.remove("hidden");
  } catch (e) {
    showToast("Failed to fetch settings (check API key if auth is required)");
    settingsModal.classList.remove("hidden");
  }
});
closeSettingsBtn.addEventListener("click", () => settingsModal.classList.add("hidden"));

// 8. Clipboard Actions
copyTagsBtn.addEventListener("click", () => {
  if (currentVideoData && currentVideoData.tags) {
    navigator.clipboard.writeText(currentVideoData.tags.join(", "));
    showToast("Tags copied!");
  }
});

copyTranscriptBtn.addEventListener("click", () => {
  if (currentVideoData && currentVideoData.transcript) {
    const txt = currentVideoData.transcript.map((t) => `[${t.timestamp}] ${t.text}`).join("\n");
    navigator.clipboard.writeText(txt);
    showToast("Transcript copied!");
  }
});

copyDescBtn.addEventListener("click", () => {
  if (currentVideoData && currentVideoData.description) {
    navigator.clipboard.writeText(currentVideoData.description);
    showToast("Description copied!");
  }
});

// 9. OS Launchers
openFolderBtn.addEventListener("click", () =>
  fetch(`${API_BASE}/api/open-folder`, { method: "POST", headers: { ...authHeaders() } })
);
openFolderActionBtn.addEventListener("click", () =>
  fetch(`${API_BASE}/api/open-folder`, { method: "POST", headers: { ...authHeaders() } })
);

if (openAudacityBtn) openAudacityBtn.addEventListener("click", () => triggerAudacity());
if (openAudacityActionBtn) openAudacityActionBtn.addEventListener("click", () => triggerAudacity());

async function triggerAudacity() {
  try {
    const res = await fetch(`${API_BASE}/api/open-audacity`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail);
    }
    showToast("Audacity launched!");
  } catch (e) {
    showToast(e.message || "Failed to launch Audacity");
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ==========================================================================
// Theme Engine (Color Theory: OLED Pure Black & Titanium Light Mode)
// ==========================================================================

function initTheme() {
  const saved = localStorage.getItem("extractor_theme") || "dark";
  applyTheme(saved);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const next = current === "light" ? "dark" : "light";
      applyTheme(next);
      localStorage.setItem("extractor_theme", next);
      showToast(`Switched to ${next === "light" ? "Light" : "Pure Black"} mode`);
    });
  }
}

function applyTheme(theme) {
  if (theme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
    if (themeIcon) themeIcon.textContent = "🌙";
    if (themeLabel) themeLabel.textContent = "Dark";
  } else {
    document.documentElement.removeAttribute("data-theme");
    if (themeIcon) themeIcon.textContent = "☀️";
    if (themeLabel) themeLabel.textContent = "Light";
  }
}

// ==========================================================================
// Modern Description Workspace Engine
// ==========================================================================

let rawDescriptionText = "";
let isDescExpanded = false;

function formatDescriptionText(text, searchQuery = "") {
  if (!text) return "<p class='empty-text'>No description provided for this video.</p>";

  // Clean and split lines
  const lines = text.split(/\r?\n/);
  const formattedLines = lines.map((line) => {
    let escaped = escapeHtml(line);

    // Turn URLs into clickable links (safely)
    escaped = escaped.replace(
      /(https?:\/\/[^\s<]+)/gi,
      '<a href="$1" target="_blank" rel="noopener noreferrer" class="desc-link">$1</a>'
    );

    // Turn Timestamps (e.g. 01:23, 1:23:45) into interactive jump chips
    escaped = escaped.replace(
      /\b((?:(?:\d{1,2}:)?\d{1,2}):\d{2})\b/g,
      (match, timeStr) => {
        const secs = parseTimeToSeconds(timeStr);
        if (secs !== null) {
          return `<button type="button" class="desc-timestamp-chip" data-time="${secs}" title="Jump trimmer to ${timeStr}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 3px;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>${timeStr}</button>`;
        }
        return match;
      }
    );

    // Highlight search matches
    if (searchQuery) {
      const cleanQ = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(`(${cleanQ})`, "gi");
      escaped = escaped.replace(regex, "<mark class='highlight'>$1</mark>");
    }

    return escaped;
  });

  return formattedLines.join("\n");
}

function renderDescription(descText) {
  rawDescriptionText = descText || "";
  const lines = rawDescriptionText ? rawDescriptionText.split(/\r?\n/).length : 0;
  if (descLineCount) descLineCount.textContent = `${lines} ${lines === 1 ? "line" : "lines"}`;

  isDescExpanded = true;
  if (videoDescWrapper) {
    videoDescWrapper.classList.remove("collapsed");
    videoDescWrapper.classList.add("expanded");
  }
  if (toggleDescExpandBtn) {
    toggleDescExpandBtn.textContent = "↑ Collapse";
  }
  if (descSearchRow) descSearchRow.classList.add("hidden");
  if (descSearchInput) descSearchInput.value = "";
  if (descSearchMatchCount) descSearchMatchCount.classList.add("hidden");

  updateDescriptionHTML();
}

function updateDescriptionHTML(query = "") {
  if (!videoDesc) return;
  videoDesc.innerHTML = formatDescriptionText(rawDescriptionText, query);

  // Bind timestamp chip clicks to interactive video trimmer
  videoDesc.querySelectorAll(".desc-timestamp-chip").forEach((chip) => {
    chip.addEventListener("click", (e) => {
      e.stopPropagation();
      const timeVal = parseFloat(chip.getAttribute("data-time"));
      if (!isNaN(timeVal) && totalDurationSeconds > 0) {
        if (!isTrimmerEnabled && toggleTrimmerBtn) {
          toggleTrimmerBtn.click();
        }
        // Set trimmer start to this timestamp
        const pct = Math.min(100, Math.max(0, (timeVal / totalDurationSeconds) * 100));
        if (rangeStart) {
          rangeStart.value = pct;
          updateTrimmerUI();
          showToast(`Trimmer start set to ${formatSecondsToTime(timeVal)}`);
        }
      }
    });
  });
}

// Description UI Listeners
if (toggleDescExpandBtn) {
  toggleDescExpandBtn.addEventListener("click", () => {
    isDescExpanded = !isDescExpanded;
    if (videoDescWrapper) {
      if (isDescExpanded) {
        videoDescWrapper.classList.remove("collapsed");
        videoDescWrapper.classList.add("expanded");
        toggleDescExpandBtn.textContent = "↑ Collapse";
      } else {
        videoDescWrapper.classList.add("collapsed");
        videoDescWrapper.classList.remove("expanded");
        toggleDescExpandBtn.textContent = "↕ Expand";
      }
    }
  });
}

if (toggleDescSearchBtn) {
  toggleDescSearchBtn.addEventListener("click", () => {
    if (!descSearchRow) return;
    const isHidden = descSearchRow.classList.contains("hidden");
    if (isHidden) {
      descSearchRow.classList.remove("hidden");
      if (descSearchInput) descSearchInput.focus();
    } else {
      descSearchRow.classList.add("hidden");
      if (descSearchInput) descSearchInput.value = "";
      updateDescriptionHTML("");
    }
  });
}

if (descSearchInput) {
  descSearchInput.addEventListener("input", () => {
    const q = descSearchInput.value.trim();
    updateDescriptionHTML(q);
    if (q) {
      const matches = (rawDescriptionText.match(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi")) || []).length;
      if (descSearchMatchCount) {
        descSearchMatchCount.textContent = `${matches} ${matches === 1 ? "match" : "matches"}`;
        descSearchMatchCount.classList.remove("hidden");
      }
    } else {
      if (descSearchMatchCount) descSearchMatchCount.classList.add("hidden");
    }
  });
}

// Initial Load
initTheme();
restoreInputCache();
loadHistory();
refreshSystemStatus();

