// ==========================================================================
// THE EXTRACTOR — HUMAN-BABY INTUITIVE CLIENT CONTROLLER
// Supports: Snippet trimming, comments search, selective downloads,
// custom folder destination, transcript search, and JSON export.
// ==========================================================================

const API_BASE = "";

// State
let apiKey = sessionStorage.getItem("extractor_api_key") || "";
let currentVideoData = null;
let currentComments = [];
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

// ---------------------------------------------------------------------------
// DOM Elements
// ---------------------------------------------------------------------------

// Tabs
const tabSingle = document.getElementById("tabSingle");
const tabBatch = document.getElementById("tabBatch");
const singleInputCard = document.getElementById("singleInputCard");
const batchInputCard = document.getElementById("batchInputCard");

// Single Mode Input
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
const batchFolderInput = document.getElementById("batchFolderInput");
const batchQueueSection = document.getElementById("batchQueueSection");
const queueList = document.getElementById("queueList");
const clearQueueBtn = document.getElementById("clearQueueBtn");
const cancelAllBtn = document.getElementById("cancelAllBtn");
const queueSummaryText = document.getElementById("queueSummaryText");
const cntQueued = document.getElementById("cntQueued");
const cntRunning = document.getElementById("cntRunning");
const cntCompleted = document.getElementById("cntCompleted");
const cntFailed = document.getElementById("cntFailed");

// Preview & Metadata Elements
const videoThumb = document.getElementById("videoThumb");
const videoDuration = document.getElementById("videoDuration");
const videoTitle = document.getElementById("videoTitle");
const videoChannel = document.getElementById("videoChannel");
const videoViews = document.getElementById("videoViews");
const videoDate = document.getElementById("videoDate");
const videoDesc = document.getElementById("videoDesc");

// Snippet & Trimmer Controls
const toggleSnippetBtn = document.getElementById("toggleSnippetBtn");
const snippetControls = document.getElementById("snippetControls");
const snippetStart = document.getElementById("snippetStart");
const snippetEnd = document.getElementById("snippetEnd");
const resetSnippetBtn = document.getElementById("resetSnippetBtn");
let isSnippetActive = false;

// Custom Folder & Options
const customFolderInput = document.getElementById("customFolderInput");
const selResolution = document.getElementById("selResolution");
const selAudio = document.getElementById("selAudio");
const optVideo = document.getElementById("optVideo");
const optAudio = document.getElementById("optAudio");
const optDoc = document.getElementById("optDoc");
const optJson = document.getElementById("optJson");
const downloadBtn = document.getElementById("downloadBtn");

// Quick Selection Helpers
const selectAllBtn = document.getElementById("selectAllBtn");
const selectOnlyAudioBtn = document.getElementById("selectOnlyAudioBtn");
const selectOnlyVideoBtn = document.getElementById("selectOnlyVideoBtn");

// Inspector Tabs & Panes
const inspectTabTranscript = document.getElementById("inspectTabTranscript");
const inspectTabComments = document.getElementById("inspectTabComments");
const inspectTabTags = document.getElementById("inspectTabTags");
const paneTranscript = document.getElementById("paneTranscript");
const paneComments = document.getElementById("paneComments");
const paneTags = document.getElementById("paneTags");

// Transcript Search & Display
const transcriptSearchInput = document.getElementById("transcriptSearchInput");
const copyTranscriptBtn = document.getElementById("copyTranscriptBtn");
const transcriptContainer = document.getElementById("transcriptContainer");

// Comments Search & Display
const commentSearchInput = document.getElementById("commentSearchInput");
const loadCommentsBtn = document.getElementById("loadCommentsBtn");
const commentsContainer = document.getElementById("commentsContainer");

// Tags
const tagsContainer = document.getElementById("tagsContainer");
const tagsCount = document.getElementById("tagsCount");
const copyTagsBtn = document.getElementById("copyTagsBtn");
const copyDescBtn = document.getElementById("copyDescBtn");

// Progress Elements
const progressCard = document.getElementById("progressCard");
const progressBar = document.getElementById("progressBar");
const progressPercent = document.getElementById("progressPercent");
const progressPhaseText = document.getElementById("progressPhaseText");
const progressSpeed = document.getElementById("progressSpeed");
const progressEta = document.getElementById("progressEta");
const finishedActions = document.getElementById("finishedActions");

// Quick OS Action Launchers
const openFolderBtn = document.getElementById("openFolderBtn");
const openAudacityBtn = document.getElementById("openAudacityBtn");
const openFolderActionBtn = document.getElementById("openFolderActionBtn");
const openAudacityActionBtn = document.getElementById("openAudacityActionBtn");

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

// System Alerts
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
const toast = document.getElementById("toast");

// ---------------------------------------------------------------------------
// Helpers & Utilities
// ---------------------------------------------------------------------------

function showToast(msg) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 2500);
}

function showError(msg) {
  if (!errorMessage || !errorBanner) return;
  errorMessage.textContent = msg;
  errorBanner.classList.remove("hidden");
  if (inspectLoader) inspectLoader.classList.add("hidden");
}

function clearError() {
  if (errorBanner) errorBanner.classList.add("hidden");
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

/**
 * Parses user input timestamp (e.g., "1:30", "01:45", "90", "90s") into seconds float.
 */
function parseTimeToSeconds(val) {
  if (!val) return null;
  const s = String(val).trim().replace(/s$/i, "");
  if (!s) return null;
  if (s.includes(":")) {
    const parts = s.split(":").map((p) => parseFloat(p.trim()));
    if (parts.some(isNaN)) return null;
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    } else if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }
  }
  const num = parseFloat(s);
  return isNaN(num) ? null : num;
}

// ---------------------------------------------------------------------------
// Navigation & Tabs
// ---------------------------------------------------------------------------

if (tabSingle && tabBatch) {
  tabSingle.addEventListener("click", () => {
    tabSingle.classList.add("active");
    tabBatch.classList.remove("active");
    singleInputCard.classList.remove("hidden");
    batchInputCard.classList.add("hidden");
  });

  tabBatch.addEventListener("click", () => {
    tabBatch.classList.add("active");
    tabSingle.classList.remove("active");
    batchInputCard.classList.remove("hidden");
    singleInputCard.classList.add("hidden");
    if (resultSection) resultSection.classList.add("hidden");
  });
}

// ---------------------------------------------------------------------------
// Single Video Inspector
// ---------------------------------------------------------------------------

if (pasteBtn && ytUrlInput) {
  pasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        ytUrlInput.value = text.trim();
        inspectVideo();
      }
    } catch {
      ytUrlInput.focus();
      showToast("Press Ctrl+V to paste your video link");
    }
  });

  ytUrlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") inspectVideo();
  });
}

if (inspectBtn) {
  inspectBtn.addEventListener("click", () => inspectVideo());
}

async function inspectVideo() {
  const url = ytUrlInput.value.trim();
  if (!url) {
    showToast("Please enter a YouTube link");
    return;
  }

  clearError();
  if (resultSection) resultSection.classList.add("hidden");
  if (inspectLoader) inspectLoader.classList.remove("hidden");
  if (loaderStatusText) loaderStatusText.textContent = "Looking up video details...";

  try {
    const res = await fetch(`${API_BASE}/api/inspect`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ url, fetch_comments: false }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not read this video. Check the link or your network.");

    if (data.is_playlist) {
      showToast(`Playlist detected: ${data.playlist_count} videos! Switching to batch list.`);
      if (tabBatch) tabBatch.click();
      if (batchUrlsInput) {
        batchUrlsInput.value = data.items.map((i) => i.url).join("\n");
        updateBatchCount();
      }
      return;
    }

    currentVideoData = data.data;
    currentComments = [];
    renderVideoWorkspace(currentVideoData);
    if (resultSection) {
      resultSection.classList.remove("hidden");
      resultSection.scrollIntoView({ behavior: "smooth" });
    }
  } catch (err) {
    showError(err.message);
  } finally {
    if (inspectLoader) inspectLoader.classList.add("hidden");
  }
}

function renderVideoWorkspace(v) {
  if (videoThumb) videoThumb.src = v.thumbnail || "";
  if (videoDuration) videoDuration.textContent = v.duration_str || "00:00";
  if (videoTitle) videoTitle.textContent = v.title || "Video";
  if (videoChannel) videoChannel.textContent = v.uploader || "Unknown Channel";
  if (videoViews) videoViews.textContent = (v.view_count ? Number(v.view_count).toLocaleString() : "0") + " views";
  if (videoDate) videoDate.textContent = v.upload_date || "Unknown Date";
  if (videoDesc) videoDesc.textContent = v.description || "No description provided.";

  // Reset Snippet inputs
  if (snippetStart) snippetStart.value = "";
  if (snippetEnd) snippetEnd.value = "";
  if (snippetControls) snippetControls.classList.add("hidden");
  isSnippetActive = false;
  if (toggleSnippetBtn) {
    toggleSnippetBtn.textContent = "✂️ Enable Snippet Trimming";
    toggleSnippetBtn.classList.remove("active");
  }

  // Tags
  renderTags(v.tags || []);

  // Transcripts
  renderTranscript(v.transcript || []);

  // Reset Comments pane
  resetCommentsUI();

  // Reset Progress View
  if (progressCard) progressCard.classList.add("hidden");
  if (finishedActions) finishedActions.classList.add("hidden");
  if (progressBar) progressBar.style.width = "0%";
}

function renderTags(tags) {
  if (!tagsContainer) return;
  tagsContainer.innerHTML = "";
  if (tagsCount) tagsCount.textContent = tags.length;

  if (tags.length > 0) {
    tags.forEach((tag) => {
      const badge = document.createElement("span");
      badge.className = "tag-badge";
      badge.textContent = "#" + tag;
      tagsContainer.appendChild(badge);
    });
  } else {
    tagsContainer.innerHTML = "<span class='empty-text'>No hidden tags found for this video.</span>";
  }
}

function renderTranscript(transcriptList) {
  if (!transcriptContainer) return;
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
      : "<p class='empty-text'>No captions or spoken transcript available.</p>";
  }
}

if (transcriptSearchInput) {
  transcriptSearchInput.addEventListener("input", () => {
    if (currentVideoData) {
      renderTranscript(currentVideoData.transcript || []);
    }
  });
}

// ---------------------------------------------------------------------------
// Comments Inspection & Search
// ---------------------------------------------------------------------------

function resetCommentsUI() {
  if (!commentsContainer) return;
  commentsContainer.innerHTML = `
    <div class="empty-placeholder">
      <span class="placeholder-emoji">💬</span>
      <p>Click <strong>Load Comments</strong> to fetch top discussions and search through what viewers said.</p>
    </div>
  `;
  if (commentSearchInput) commentSearchInput.value = "";
  if (loadCommentsBtn) {
    loadCommentsBtn.disabled = false;
    loadCommentsBtn.textContent = "💬 Load Comments";
  }
}

if (loadCommentsBtn) {
  loadCommentsBtn.addEventListener("click", async () => {
    if (!currentVideoData || !currentVideoData.url) {
      showToast("Inspect a video link first!");
      return;
    }

    try {
      loadCommentsBtn.disabled = true;
      loadCommentsBtn.textContent = "⏳ Loading...";
      commentsContainer.innerHTML = `
        <div class="empty-placeholder">
          <span class="placeholder-emoji">⏳</span>
          <p>Fetching top viewer comments from YouTube...</p>
        </div>
      `;

      const res = await fetch(`${API_BASE}/api/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ url: currentVideoData.url, max_comments: 60 }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not fetch comments");

      currentComments = data.comments || [];
      renderCommentsList();
      showToast(`Loaded ${currentComments.length} comments!`);
    } catch (err) {
      showToast(`Error: ${err.message}`);
      resetCommentsUI();
    } finally {
      loadCommentsBtn.disabled = false;
      loadCommentsBtn.textContent = "🔄 Refresh Comments";
    }
  });
}

function renderCommentsList() {
  if (!commentsContainer) return;
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
      card.className = "comment-item-card";

      let textHtml = escapeHtml(c.text);
      if (query) {
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
        textHtml = textHtml.replace(regex, "<mark class='highlight'>$1</mark>");
      }

      card.innerHTML = `
        <div class="comment-author-row">
          <span class="comment-author">@${escapeHtml(c.author)}</span>
          ${c.likes ? `<span class="comment-likes">👍 ${c.likes}</span>` : ""}
        </div>
        <div class="comment-body">${textHtml}</div>
      `;
      commentsContainer.appendChild(card);
    });
  } else {
    commentsContainer.innerHTML = query
      ? `<p class='empty-text'>No comments matched "${escapeHtml(query)}".</p>`
      : "<p class='empty-text'>No comments available for this video.</p>";
  }
}

if (commentSearchInput) {
  commentSearchInput.addEventListener("input", () => {
    if (currentComments && currentComments.length > 0) {
      renderCommentsList();
    }
  });
}

// ---------------------------------------------------------------------------
// Inspector Tabs Navigation
// ---------------------------------------------------------------------------

function switchInspectTab(activeTab, activePane) {
  [inspectTabTranscript, inspectTabComments, inspectTabTags].forEach((tab) => {
    if (tab) tab.classList.remove("active");
  });
  [paneTranscript, paneComments, paneTags].forEach((pane) => {
    if (pane) pane.classList.add("hidden");
  });

  if (activeTab) activeTab.classList.add("active");
  if (activePane) activePane.classList.remove("hidden");
}

if (inspectTabTranscript) {
  inspectTabTranscript.addEventListener("click", () => switchInspectTab(inspectTabTranscript, paneTranscript));
}
if (inspectTabComments) {
  inspectTabComments.addEventListener("click", () => switchInspectTab(inspectTabComments, paneComments));
}
if (inspectTabTags) {
  inspectTabTags.addEventListener("click", () => switchInspectTab(inspectTabTags, paneTags));
}

// ---------------------------------------------------------------------------
// Snippet / Trimming Controls
// ---------------------------------------------------------------------------

if (toggleSnippetBtn) {
  toggleSnippetBtn.addEventListener("click", () => {
    isSnippetActive = !isSnippetActive;
    if (isSnippetActive) {
      snippetControls.classList.remove("hidden");
      toggleSnippetBtn.textContent = "✖ Disable Snippet Trimming";
      toggleSnippetBtn.classList.add("active");
      if (snippetStart) snippetStart.focus();
    } else {
      snippetControls.classList.add("hidden");
      toggleSnippetBtn.textContent = "✂️ Enable Snippet Trimming";
      toggleSnippetBtn.classList.remove("active");
      if (snippetStart) snippetStart.value = "";
      if (snippetEnd) snippetEnd.value = "";
    }
  });
}

if (resetSnippetBtn) {
  resetSnippetBtn.addEventListener("click", () => {
    if (snippetStart) snippetStart.value = "";
    if (snippetEnd) snippetEnd.value = "";
    showToast("Reset to full video range");
  });
}

// ---------------------------------------------------------------------------
// Quick Selection Helpers
// ---------------------------------------------------------------------------

if (selectAllBtn) {
  selectAllBtn.addEventListener("click", () => {
    if (optVideo) optVideo.checked = true;
    if (optAudio) optAudio.checked = true;
    if (optDoc) optDoc.checked = true;
    if (optJson) optJson.checked = true;
    showToast("Selected all components!");
  });
}

if (selectOnlyAudioBtn) {
  selectOnlyAudioBtn.addEventListener("click", () => {
    if (optVideo) optVideo.checked = false;
    if (optAudio) optAudio.checked = true;
    if (optDoc) optDoc.checked = false;
    if (optJson) optJson.checked = false;
    showToast("Selected audio only!");
  });
}

if (selectOnlyVideoBtn) {
  selectOnlyVideoBtn.addEventListener("click", () => {
    if (optVideo) optVideo.checked = true;
    if (optAudio) optAudio.checked = false;
    if (optDoc) optDoc.checked = false;
    if (optJson) optJson.checked = false;
    showToast("Selected video only!");
  });
}

// ---------------------------------------------------------------------------
// Single Video Download Execution
// ---------------------------------------------------------------------------

if (downloadBtn) {
  downloadBtn.addEventListener("click", async () => {
    if (!currentVideoData) {
      showToast("Please inspect a video first!");
      return;
    }

    const hasAnySelection =
      (optVideo && optVideo.checked) ||
      (optAudio && optAudio.checked) ||
      (optDoc && optDoc.checked) ||
      (optJson && optJson.checked);

    if (!hasAnySelection) {
      showToast("Please check at least one box (Video, Music, Document, or JSON)!");
      return;
    }

    const [audioCodec, audioBitrate] = selAudio ? selAudio.value.split("-") : ["mp3", "192"];

    // Snippet range parsing
    let startTime = null;
    let endTime = null;
    if (isSnippetActive) {
      if (snippetStart && snippetStart.value) {
        startTime = parseTimeToSeconds(snippetStart.value);
        if (startTime === null) {
          showError("Start time is invalid. Use seconds (e.g. 30) or MM:SS (e.g. 1:15).");
          return;
        }
      }
      if (snippetEnd && snippetEnd.value) {
        endTime = parseTimeToSeconds(snippetEnd.value);
        if (endTime === null) {
          showError("End time is invalid. Use seconds (e.g. 90) or MM:SS (e.g. 2:00).");
          return;
        }
      }
      if (startTime !== null && endTime !== null && startTime >= endTime) {
        showError("Start time must come before end time!");
        return;
      }
    }

    // Destination folder
    const outputDir = customFolderInput ? customFolderInput.value.trim() || null : null;

    const payload = {
      url: currentVideoData.url,
      download_video: optVideo ? optVideo.checked : false,
      download_audio: optAudio ? optAudio.checked : false,
      download_doc: optDoc ? optDoc.checked : false,
      download_json: optJson ? optJson.checked : false,
      video_resolution: selResolution ? selResolution.value : "best",
      audio_format: audioCodec,
      audio_bitrate: audioBitrate,
      start_time: startTime,
      end_time: endTime,
      output_dir: outputDir,
    };

    clearError();
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
      if (progressCard) progressCard.classList.remove("hidden");
      if (finishedActions) finishedActions.classList.add("hidden");
      startProgressPolling(activeTaskId);
    } catch (err) {
      showError(err.message);
      downloadBtn.disabled = false;
    }
  });
}

function startProgressPolling(taskId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/progress/${taskId}`, {
        headers: { ...authHeaders() },
      });
      if (!res.ok) return;

      const info = await res.json();
      if (progressBar) progressBar.style.width = info.percent || "0%";
      if (progressPercent) progressPercent.textContent = info.percent || "0%";
      if (progressPhaseText) progressPhaseText.textContent = info.message || "Processing...";
      if (progressSpeed) progressSpeed.textContent = info.speed ? `Speed: ${info.speed}` : "Speed: --";
      if (progressEta) progressEta.textContent = info.eta ? `Remaining: ${info.eta}` : "Time: --";

      if (info.status === "completed") {
        clearInterval(pollTimer);
        pollTimer = null;
        if (downloadBtn) downloadBtn.disabled = false;
        if (finishedActions) finishedActions.classList.remove("hidden");
        loadHistory();
        refreshSystemStatus();
      } else if (info.status === "cancelled") {
        clearInterval(pollTimer);
        pollTimer = null;
        if (downloadBtn) downloadBtn.disabled = false;
        showToast(info.message || "Download was cancelled");
      } else if (info.status === "error" || info.status === "interrupted") {
        clearInterval(pollTimer);
        pollTimer = null;
        if (downloadBtn) downloadBtn.disabled = false;
        showError(info.message || `Download ${info.status}`);
      }
    } catch (e) {
      console.error("Progress check error:", e);
    }
  }, 500);
}

// ---------------------------------------------------------------------------
// Batch Operations
// ---------------------------------------------------------------------------

if (batchPasteBtn && batchUrlsInput) {
  batchPasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        batchUrlsInput.value = text.trim();
        updateBatchCount();
      }
    } catch {
      batchUrlsInput.focus();
    }
  });

  batchUrlsInput.addEventListener("input", updateBatchCount);
}

function getBatchUrls() {
  if (!batchUrlsInput) return [];
  const raw = batchUrlsInput.value.trim();
  if (!raw) return [];
  return raw
    .split(/[\n,]+/)
    .map((u) => u.trim())
    .filter((u) => /^https?:\/\//i.test(u));
}

function updateBatchCount() {
  const urls = getBatchUrls();
  if (batchCount) batchCount.textContent = urls.length;
}

if (startBatchBtn) {
  startBatchBtn.addEventListener("click", async () => {
    const urls = getBatchUrls();
    if (!urls.length) {
      showToast("Please enter at least one valid video link");
      return;
    }

    const [audioCodec, audioBitrate] = selAudio ? selAudio.value.split("-") : ["mp3", "192"];
    const outputDir = batchFolderInput ? batchFolderInput.value.trim() || null : null;

    const payload = {
      urls: urls,
      download_video: optVideo ? optVideo.checked : true,
      download_audio: optAudio ? optAudio.checked : true,
      download_doc: optDoc ? optDoc.checked : true,
      download_json: optJson ? optJson.checked : false,
      video_resolution: selResolution ? selResolution.value : "best",
      audio_format: audioCodec,
      audio_bitrate: audioBitrate,
      output_dir: outputDir,
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
      if (batchQueueSection) batchQueueSection.classList.remove("hidden");

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
      if (batchUrlsInput) batchUrlsInput.value = "";
      updateBatchCount();
    } catch (err) {
      showError(err.message);
    } finally {
      startBatchBtn.disabled = false;
      startBatchBtn.textContent = `🚀 Start Batch Download (${getBatchUrls().length} items)`;
    }
  });
}

function renderQueue() {
  if (!queueList) return;
  queueList.innerHTML = "";
  let qCnt = 0, rCnt = 0, cCnt = 0, fCnt = 0;

  activeTasksMap.forEach((task) => {
    if (task.status === "queued") qCnt++;
    else if (task.status === "running") rCnt++;
    else if (task.status === "completed") cCnt++;
    else if (task.status === "error" || task.status === "cancelled") fCnt++;

    const item = document.createElement("div");
    item.className = "queue-item";
    const displayStatus = task.status === "queued" ? "queued" : task.status;
    const badgeClass = task.status === "queued" ? "status-waiting" : `status-${task.status}`;

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

window.cancelTask = async function (taskId) {
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
    showToast(`Failed to cancel: ${e.message}`);
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
      showToast(`Failed: ${e.message}`);
    }
  });
}

function startBatchPolling() {
  if (batchPollTimer) return;
  batchPollTimer = setInterval(async () => {
    try {
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
    } catch {}

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
      refreshSystemStatus();
      showToast("Batch processing finished!");
    }
  }, 1000);
}

if (clearQueueBtn) {
  clearQueueBtn.addEventListener("click", () => {
    for (const [id, t] of activeTasksMap.entries()) {
      if (t.status === "completed" || t.status === "error" || t.status === "cancelled") {
        activeTasksMap.delete(id);
      }
    }
    renderQueue();
    if (activeTasksMap.size === 0 && batchQueueSection) batchQueueSection.classList.add("hidden");
  });
}

// ---------------------------------------------------------------------------
// History Drawer & Management
// ---------------------------------------------------------------------------

if (navHistoryBtn) {
  navHistoryBtn.addEventListener("click", () => {
    loadHistory();
    if (historyModal) historyModal.classList.remove("hidden");
  });
}

if (closeHistoryBtn) {
  closeHistoryBtn.addEventListener("click", () => {
    if (historyModal) historyModal.classList.add("hidden");
  });
}

let historySearchTimer = null;
if (historySearchInput) {
  historySearchInput.addEventListener("input", () => {
    const query = historySearchInput.value.trim();
    if (clearSearchBtn) {
      if (query) clearSearchBtn.classList.remove("hidden");
      else clearSearchBtn.classList.add("hidden");
    }
    clearTimeout(historySearchTimer);
    historySearchTimer = setTimeout(() => {
      loadHistory(query);
    }, 250);
  });
}

if (clearSearchBtn) {
  clearSearchBtn.addEventListener("click", () => {
    if (historySearchInput) historySearchInput.value = "";
    clearSearchBtn.classList.add("hidden");
    loadHistory();
  });
}

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
    if (!searchQuery && historyCountBadge) {
      historyCountBadge.textContent = data.total !== undefined ? data.total : records.length;
    }

    if (!records.length) {
      if (historyListContainer) {
        historyListContainer.innerHTML = searchQuery
          ? `<p class='empty-state'>No matching records found for "${escapeHtml(searchQuery)}".</p>`
          : "<p class='empty-state'>No extraction history yet. Paste a link to get started!</p>";
      }
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
    if (historyListContainer) historyListContainer.innerHTML = html;
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
    loadHistory(historySearchInput ? historySearchInput.value.trim() || null : null);
    refreshSystemStatus();
    showToast("Record deleted");
  } catch {
    showToast("Failed to delete record");
  }
};

if (clearHistoryBtn) {
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
    } catch {
      showToast("Failed to clear history");
    }
  });
}

// ---------------------------------------------------------------------------
// System Settings, Alerts & Config
// ---------------------------------------------------------------------------

async function refreshSystemStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/config`, {
      headers: { ...authHeaders() },
    });
    if (!res.ok) return;
    const cfg = await res.json();

    if (cfg.storage && diskUsageText) {
      const mb = cfg.storage.total_mb;
      const count = cfg.storage.file_count;
      const freeGb = cfg.storage.disk_free_gb;
      diskUsageText.textContent = `${mb} MB (${count} files) • ${freeGb} GB Free`;

      if (diskBadge) {
        if (cfg.storage.max_storage_gb > 0 && cfg.storage.total_gb >= cfg.storage.max_storage_gb * 0.85) {
          diskBadge.classList.add("disk-warn");
        } else {
          diskBadge.classList.remove("disk-warn");
        }
      }
    }

    if (cfg.ytdlp && cfg.ytdlp.is_outdated) {
      if (ytdlpCurrentVer) ytdlpCurrentVer.textContent = cfg.ytdlp.installed;
      if (ytdlpLatestVer) ytdlpLatestVer.textContent = cfg.ytdlp.latest;
      if (ytdlpAlertBanner) ytdlpAlertBanner.classList.remove("hidden");
    } else if (ytdlpAlertBanner) {
      ytdlpAlertBanner.classList.add("hidden");
    }

    if (cfg.js_runtime_available === false) {
      if (jsAlertBanner) jsAlertBanner.classList.remove("hidden");
    } else if (jsAlertBanner) {
      jsAlertBanner.classList.add("hidden");
    }

    if (cfg.ffmpeg_available === false) {
      if (ffmpegAlertBanner) ffmpegAlertBanner.classList.remove("hidden");
    } else if (ffmpegAlertBanner) {
      ffmpegAlertBanner.classList.add("hidden");
    }

    return cfg;
  } catch {
    if (diskUsageText) diskUsageText.textContent = "Disk: --";
  }
}

if (dismissYtdlpAlert) {
  dismissYtdlpAlert.addEventListener("click", () => ytdlpAlertBanner.classList.add("hidden"));
}
if (dismissJsAlert) {
  dismissJsAlert.addEventListener("click", () => jsAlertBanner.classList.add("hidden"));
}
if (dismissFfmpegAlert) {
  dismissFfmpegAlert.addEventListener("click", () => ffmpegAlertBanner.classList.add("hidden"));
}

if (navSettingsBtn) {
  navSettingsBtn.addEventListener("click", async () => {
    try {
      const cfg = await refreshSystemStatus();
      if (!cfg) throw new Error("Could not load config");

      const storage = cfg.storage || {};
      const ytdlp = cfg.ytdlp || {};

      settingsContent.innerHTML = `
        <div style="font-size: 0.95rem; line-height: 1.7;">
          <p><strong>Downloads Directory:</strong> <code>${escapeHtml(cfg.download_dir)}</code></p>
          <p><strong>Log File:</strong> <code>${escapeHtml(cfg.log_file || "extractor.log")}</code></p>
          <p><strong>Disk Storage:</strong> <code>${storage.total_mb || 0} MB</code> (${storage.file_count || 0} files) | Drive Free: <code>${storage.disk_free_gb || 0} GB</code></p>
          <p><strong>Retention Policy:</strong> ${storage.max_storage_gb > 0 ? `Max ${storage.max_storage_gb} GB` : "No size cap"} | ${storage.delete_after_days > 0 ? `Auto-purge > ${storage.delete_after_days} days` : "Never purge by age"}</p>
          <p><strong>yt-dlp Engine:</strong> <code>v${escapeHtml(ytdlp.installed || "unknown")}</code> ${ytdlp.is_outdated ? `⚠️ (Newer version ${ytdlp.latest} available!)` : "✅ Up to date"}</p>
          <p><strong>JS Runtime (YouTube):</strong> ${cfg.js_runtime_available ? "✅ Detected (Deno/Node/Bun/QuickJS)" : "⚠️ Not Found (Required for YouTube challenges)"}</p>
          <p><strong>FFmpeg Suite:</strong> ${cfg.ffmpeg_available ? "✅ Detected" : "⚠️ Not Found (Required for video/audio merges)"}</p>
          <p><strong>Audacity Binary:</strong> <code>${escapeHtml(cfg.audacity_path)}</code> (${cfg.audacity_detected ? "✅ Detected" : "⚠️ Not Found"})</p>
          <p><strong>Cookies Configured:</strong> ${cfg.has_cookies ? "✅ Yes (cookies.txt)" : "❌ No"}</p>
          <p><strong>API Auth Enabled:</strong> ${cfg.auth_enabled ? "🔒 Yes" : "🔓 Public / Local"}</p>

          <div style="margin-top: 1.25rem; padding: 0.85rem; background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center;">
            <div>
              <strong>Storage Maintenance</strong>
              <p style="font-size: 0.8rem; color: var(--text-muted); margin: 0;">Prune old downloads according to retention policy.</p>
            </div>
            <button id="runCleanupBtn" class="btn btn-secondary btn-sm">🧹 Run Cleanup Now</button>
          </div>

          <div style="margin-top: 1.25rem; padding-top: 1rem; border-top: 1px solid var(--border-subtle);">
            <label style="display: block; font-weight: 600; margin-bottom: 0.4rem;" for="apiKeyInput">
              🔑 Client API Key (Header: X-API-Key):
            </label>
            <div style="display: flex; gap: 0.5rem;">
              <input 
                type="password" 
                id="apiKeyInput" 
                value="${escapeHtml(apiKey)}" 
                placeholder="Enter API Key if configured..." 
                style="flex: 1; background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 0.5rem; color: var(--text-pure); font-family: var(--font-mono); font-size: 0.85rem;"
              />
              <button id="saveApiKeyBtn" class="btn btn-primary btn-sm">Save Key</button>
            </div>
            <p style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.35rem;">Saved in your browser session for authenticated API calls.</p>
          </div>
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
        } catch {
          showToast("Storage cleanup failed");
        }
      });

      settingsModal.classList.remove("hidden");
    } catch {
      showToast("Failed to fetch settings");
      settingsModal.classList.remove("hidden");
    }
  });
}

if (closeSettingsBtn) {
  closeSettingsBtn.addEventListener("click", () => {
    if (settingsModal) settingsModal.classList.add("hidden");
  });
}

// ---------------------------------------------------------------------------
// Clipboard Quick Buttons
// ---------------------------------------------------------------------------

if (copyTagsBtn) {
  copyTagsBtn.addEventListener("click", () => {
    if (currentVideoData && currentVideoData.tags) {
      navigator.clipboard.writeText(currentVideoData.tags.join(", "));
      showToast("Tags copied!");
    }
  });
}

if (copyTranscriptBtn) {
  copyTranscriptBtn.addEventListener("click", () => {
    if (currentVideoData && currentVideoData.transcript) {
      const txt = currentVideoData.transcript.map((t) => `[${t.timestamp}] ${t.text}`).join("\n");
      navigator.clipboard.writeText(txt);
      showToast("Transcript copied!");
    }
  });
}

if (copyDescBtn) {
  copyDescBtn.addEventListener("click", () => {
    if (currentVideoData && currentVideoData.description) {
      navigator.clipboard.writeText(currentVideoData.description);
      showToast("Description copied!");
    }
  });
}

// ---------------------------------------------------------------------------
// OS Action Launchers
// ---------------------------------------------------------------------------

if (openFolderBtn) {
  openFolderBtn.addEventListener("click", () =>
    fetch(`${API_BASE}/api/open-folder`, { method: "POST", headers: { ...authHeaders() } })
  );
}
if (openFolderActionBtn) {
  openFolderActionBtn.addEventListener("click", () =>
    fetch(`${API_BASE}/api/open-folder`, { method: "POST", headers: { ...authHeaders() } })
  );
}

if (openAudacityBtn) {
  openAudacityBtn.addEventListener("click", () => triggerAudacity());
}
if (openAudacityActionBtn) {
  openAudacityActionBtn.addEventListener("click", () => triggerAudacity());
}

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

// Initial Boot
loadHistory();
refreshSystemStatus();
