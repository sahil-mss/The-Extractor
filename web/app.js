// ==========================================================================
// THE EXTRACTOR — V2.5 CLIENT SCRIPT (BATCH, HISTORY & FORMATS)
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
const transcriptStatus = document.getElementById("transcriptStatus");

// Customization & Options
const selResolution = document.getElementById("selResolution");
const selAudio = document.getElementById("selAudio");
const optVideo = document.getElementById("optVideo");
const optAudio = document.getElementById("optAudio");
const optDoc = document.getElementById("optDoc");
const downloadBtn = document.getElementById("downloadBtn");

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

const navSettingsBtn = document.getElementById("navSettingsBtn");
const settingsModal = document.getElementById("settingsModal");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const settingsContent = document.getElementById("settingsContent");

// Quick Actions
const openFolderBtn = document.getElementById("openFolderBtn");
const openAudacityBtn = document.getElementById("openAudacityBtn");
const openFolderActionBtn = document.getElementById("openFolderActionBtn");
const openAudacityActionBtn = document.getElementById("openAudacityActionBtn");
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

// 1. Tab Navigation
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
  resultSection.classList.add("hidden");
});

// 2. Single Video Paste & Input
pasteBtn.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      ytUrlInput.value = text.trim();
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
    }
  } catch (err) {
    batchUrlsInput.focus();
  }
});

batchUrlsInput.addEventListener("input", updateBatchCount);

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
  activeTasksMap.forEach((task) => {
    const item = document.createElement("div");
    item.className = "queue-item";
    const displayStatus =
      task.status === "queued" ? "queued (waiting for slot)" : task.status;
    const badgeClass =
      task.status === "queued" ? "status-waiting" : `status-${task.status}`;

    item.innerHTML = `
      <div class="queue-info">
        <span class="queue-url">${escapeHtml(task.url)}</span>
        <span class="queue-status-text">${escapeHtml(task.message || task.percent || "")}</span>
      </div>
      <span class="queue-status-badge ${badgeClass}">${displayStatus}</span>
    `;
    queueList.appendChild(item);
  });
}

function startBatchPolling() {
  if (batchPollTimer) return;
  batchPollTimer = setInterval(async () => {
    let allFinished = true;
    for (const [taskId, task] of activeTasksMap.entries()) {
      if (task.status === "completed" || task.status === "error") continue;
      allFinished = false;
      try {
        const res = await fetch(`${API_BASE}/api/progress/${taskId}`, {
          headers: { ...authHeaders() },
        });
        if (res.ok) {
          const update = await res.json();
          activeTasksMap.set(taskId, { ...task, ...update });
        }
      } catch (e) {}
    }
    renderQueue();
    if (allFinished) {
      clearInterval(batchPollTimer);
      batchPollTimer = null;
      loadHistory();
      showToast("Batch processing completed!");
    }
  }, 1000);
}

clearQueueBtn.addEventListener("click", () => {
  for (const [id, t] of activeTasksMap.entries()) {
    if (t.status === "completed" || t.status === "error") {
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

    inspectLoader.classList.add("hidden");

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
  }
}

function renderVideoWorkspace(v) {
  videoThumb.src = v.thumbnail;
  videoDuration.textContent = v.duration_str;
  videoTitle.textContent = v.title;
  videoChannel.textContent = v.uploader;
  videoViews.textContent = Number(v.view_count).toLocaleString() + " views";
  videoDate.textContent = v.upload_date || "Unknown Date";
  videoDesc.textContent = v.description || "No description provided.";

  // Tags
  tagsContainer.innerHTML = "";
  tagsCount.textContent = v.tags ? v.tags.length : 0;
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
  transcriptContainer.innerHTML = "";
  if (v.has_transcript && v.transcript.length > 0) {
    transcriptStatus.textContent = `${v.transcript.length} lines`;
    v.transcript.forEach((t) => {
      const row = document.createElement("div");
      row.className = "transcript-item";
      row.innerHTML = `<span class="transcript-timestamp">[${t.timestamp}]</span> ${escapeHtml(t.text)}`;
      transcriptContainer.appendChild(row);
    });
  } else {
    transcriptStatus.textContent = "None";
    transcriptContainer.innerHTML = "<p class='empty-text'>No captions or transcript available.</p>";
  }

  // Reset Progress Card
  progressCard.classList.add("hidden");
  finishedActions.classList.add("hidden");
  progressBar.style.width = "0%";
}

// 5. Download Execution (Single)
downloadBtn.addEventListener("click", async () => {
  if (!currentVideoData) return;
  const [audioCodec, audioBitrate] = selAudio.value.split("-");

  const payload = {
    url: currentVideoData.url,
    download_video: optVideo.checked,
    download_audio: optAudio.checked,
    download_doc: optDoc.checked,
    video_resolution: selResolution.value,
    audio_format: audioCodec,
    audio_bitrate: audioBitrate,
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
      } else if (info.status === "error") {
        clearInterval(pollTimer);
        pollTimer = null;
        downloadBtn.disabled = false;
        showError(info.message);
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

async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/history`, {
      headers: { ...authHeaders() },
    });
    if (!res.ok) return;
    const data = await res.json();
    const records = data.history || [];
    historyCountBadge.textContent = records.length;

    if (!records.length) {
      historyListContainer.innerHTML = "<p class='empty-state'>No extraction history yet.</p>";
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
            <button class="btn btn-ghost btn-sm" onclick="deleteHistoryItem(${r.id})">Delete</button>
          </td>
        </tr>`;
    });

    html += `</tbody></table>`;
    historyListContainer.innerHTML = html;
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

window.deleteHistoryItem = async function (id) {
  try {
    await fetch(`${API_BASE}/api/history/${id}`, {
      method: "DELETE",
      headers: { ...authHeaders() },
    });
    loadHistory();
  } catch (e) {
    showToast("Failed to delete record");
  }
};

clearHistoryBtn.addEventListener("click", async () => {
  if (confirm("Are you sure you want to clear all extraction history?")) {
    await fetch(`${API_BASE}/api/history`, {
      method: "DELETE",
      headers: { ...authHeaders() },
    });
    loadHistory();
  }
});

// 7. Settings Drawer
navSettingsBtn.addEventListener("click", async () => {
  try {
    const res = await fetch(`${API_BASE}/api/config`, {
      headers: { ...authHeaders() },
    });
    const cfg = await res.json();
    settingsContent.innerHTML = `
      <div style="font-size: 0.9rem; line-height: 1.6;">
        <p><strong>Downloads Directory:</strong> <code>${escapeHtml(cfg.download_dir)}</code></p>
        <p><strong>Audacity Binary:</strong> <code>${escapeHtml(cfg.audacity_path)}</code> (${cfg.audacity_detected ? "✅ Detected" : "⚠️ Not Found"})</p>
        <p><strong>Cookies Configured:</strong> ${cfg.has_cookies ? "✅ Yes (cookies.txt)" : "❌ No"}</p>
        <p><strong>API Auth Enabled:</strong> ${cfg.auth_enabled ? "🔒 Yes" : "🔓 Public / Local"}</p>
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
              style="flex: 1; background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 0.5rem; color: var(--text-primary); font-family: var(--font-mono); font-size: 0.85rem;"
            />
            <button id="saveApiKeyBtn" class="btn btn-primary btn-sm">Save Key</button>
          </div>
          <p style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.35rem;">Saved in your browser session for authenticated API calls.</p>
        </div>
        <p style="margin-top: 1rem; color: var(--text-secondary);">Edit <code>config.yaml</code> to adjust quality presets, Audacity path, API tokens, and concurrency.</p>
      </div>
    `;

    document.getElementById("saveApiKeyBtn").addEventListener("click", () => {
      const keyVal = document.getElementById("apiKeyInput").value;
      setApiKey(keyVal);
      showToast("API Key saved for this session!");
      loadHistory();
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

openAudacityBtn.addEventListener("click", () => triggerAudacity());
openAudacityActionBtn.addEventListener("click", () => triggerAudacity());

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

// Initial Load
loadHistory();
