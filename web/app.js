// ==========================================================================
// THE EXTRACTOR — CLIENT INTERACTION ENGINE
// ==========================================================================

const API_BASE = "";

// State
let currentVideoData = null;
let activeTaskId = null;
let pollTimer = null;

// DOM Elements
const ytUrlInput = document.getElementById("ytUrlInput");
const pasteBtn = document.getElementById("pasteBtn");
const inspectBtn = document.getElementById("inspectBtn");
const inspectLoader = document.getElementById("inspectLoader");
const errorBanner = document.getElementById("errorBanner");
const errorMessage = document.getElementById("errorMessage");
const resultSection = document.getElementById("resultSection");

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

// Option Checkboxes
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

// Action Triggers
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

// Error Utility
function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.classList.remove("hidden");
  inspectLoader.classList.add("hidden");
}

function clearError() {
  errorBanner.classList.add("hidden");
}

// 1. Clipboard Paste Handler
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

// 2. Input Enter Key
ytUrlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    inspectVideo();
  }
});

inspectBtn.addEventListener("click", () => {
  inspectVideo();
});

// 3. Inspect YouTube Video Metadata
async function inspectVideo() {
  const url = ytUrlInput.value.trim();
  if (!url) {
    showError("Please enter a valid YouTube video or shorts link.");
    return;
  }

  clearError();
  inspectLoader.classList.remove("hidden");
  resultSection.classList.add("hidden");
  progressCard.classList.add("hidden");
  finishedActions.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE}/api/inspect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to retrieve video information");
    }

    currentVideoData = data.data;
    renderVideoDetails(currentVideoData);
    inspectLoader.classList.add("hidden");
    resultSection.classList.remove("hidden");
  } catch (err) {
    showError(err.message || "An unexpected error occurred while analyzing the video.");
  }
}

// 4. Render Video Inspection Results
function renderVideoDetails(info) {
  videoThumb.src = info.thumbnail;
  videoDuration.textContent = info.duration_str;
  videoTitle.textContent = info.title;
  videoChannel.textContent = info.uploader;
  videoViews.textContent = `${Number(info.view_count || 0).toLocaleString()} views`;
  videoDate.textContent = info.upload_date || "Uploaded";
  videoDesc.textContent = info.description || "No description provided.";

  // Render Tags Cloud
  tagsContainer.innerHTML = "";
  const tags = info.tags || [];
  tagsCount.textContent = tags.length;

  if (tags.length === 0) {
    tagsContainer.innerHTML = '<span style="color: var(--text-dim); font-size: var(--text-xs);">No public tags found for this video.</span>';
  } else {
    tags.forEach((tag) => {
      const pill = document.createElement("span");
      pill.className = "tag-pill";
      pill.textContent = `#${tag}`;
      pill.title = "Click to copy tag";
      pill.addEventListener("click", () => {
        navigator.clipboard.writeText(tag);
        showToast(`Copied tag: #${tag}`);
      });
      tagsContainer.appendChild(pill);
    });
  }

  // Render Transcripts
  transcriptContainer.innerHTML = "";
  const transcript = info.transcript || [];
  if (transcript.length === 0) {
    transcriptStatus.textContent = "Unavailable";
    transcriptContainer.innerHTML = '<div style="color: var(--text-dim); font-size: var(--text-xs); padding: var(--space-2);">No subtitles or auto-captions available for this video.</div>';
  } else {
    transcriptStatus.textContent = `${transcript.length} lines`;
    transcript.forEach((line) => {
      const item = document.createElement("div");
      item.className = "transcript-item";

      const ts = document.createElement("span");
      ts.className = "ts-time";
      ts.textContent = line.timestamp;

      const txt = document.createElement("span");
      txt.className = "ts-text";
      txt.textContent = line.text;

      item.appendChild(ts);
      item.appendChild(txt);
      transcriptContainer.appendChild(item);
    });
  }
}

// 5. Trigger Download Task
downloadBtn.addEventListener("click", async () => {
  if (!currentVideoData) return;

  const url = currentVideoData.url;
  const download_video = optVideo.checked;
  const download_audio = optAudio.checked;
  const download_doc = optDoc.checked;

  if (!download_video && !download_audio && !download_doc) {
    showToast("Please select at least one package option above.");
    return;
  }

  progressCard.classList.remove("hidden");
  finishedActions.classList.add("hidden");
  progressBar.style.width = "0%";
  progressPercent.textContent = "0%";
  progressPhaseText.textContent = "Initializing download...";
  progressSpeed.textContent = "Speed: --";
  progressEta.textContent = "ETA: --";

  try {
    const res = await fetch(`${API_BASE}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        download_video,
        download_audio,
        download_doc,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to start download");
    }

    activeTaskId = data.task_id;
    startProgressPolling(activeTaskId);
  } catch (err) {
    showError(err.message || "Failed to start download task");
  }
});

// 6. Poll Task Progress
function startProgressPolling(taskId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/progress/${taskId}`);
      if (!res.ok) return;
      const data = await res.json();

      if (data.status === "running" || data.status === "queued") {
        if (data.percent) {
          progressBar.style.width = data.percent;
          progressPercent.textContent = data.percent;
        }
        if (data.message) {
          progressPhaseText.textContent = data.message;
        }
        if (data.speed) {
          progressSpeed.textContent = `Speed: ${data.speed}`;
        }
        if (data.eta) {
          progressEta.textContent = `ETA: ${data.eta}`;
        }
      } else if (data.status === "completed") {
        clearInterval(pollTimer);
        progressBar.style.width = "100%";
        progressPercent.textContent = "100%";
        progressPhaseText.textContent = "Complete!";
        progressSpeed.textContent = "Done";
        progressEta.textContent = "0s";
        finishedActions.classList.remove("hidden");
        showToast("Download and extraction completed!");
      } else if (data.status === "error") {
        clearInterval(pollTimer);
        showError(data.message || "An error occurred during download.");
      }
    } catch (err) {
      console.error("Polling error:", err);
    }
  }, 600);
}

// 7. Action Triggers
async function openFolder() {
  try {
    await fetch(`${API_BASE}/api/open-folder`, { method: "POST" });
    showToast("Opened downloads folder in File Explorer");
  } catch (err) {
    showToast("Could not open downloads folder");
  }
}

async function openAudacity() {
  try {
    const res = await fetch(`${API_BASE}/api/open-audacity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (res.ok) {
      showToast("Launched Audacity with latest audio track!");
    } else {
      showToast(data.detail || "Could not launch Audacity");
    }
  } catch (err) {
    showToast("Failed to launch Audacity");
  }
}

openFolderBtn.addEventListener("click", openFolder);
openFolderActionBtn.addEventListener("click", openFolder);
openAudacityBtn.addEventListener("click", openAudacity);
openAudacityActionBtn.addEventListener("click", openAudacity);

// 8. Copy Utilities
copyTagsBtn.addEventListener("click", () => {
  if (!currentVideoData || !currentVideoData.tags || currentVideoData.tags.length === 0) {
    showToast("No tags to copy");
    return;
  }
  const tagsStr = currentVideoData.tags.join(", ");
  navigator.clipboard.writeText(tagsStr);
  showToast(`Copied ${currentVideoData.tags.length} tags to clipboard!`);
});

copyTranscriptBtn.addEventListener("click", () => {
  if (!currentVideoData || !currentVideoData.transcript || currentVideoData.transcript.length === 0) {
    showToast("No transcript to copy");
    return;
  }
  const text = currentVideoData.transcript.map((l) => `[${l.timestamp}] ${l.text}`).join("\n");
  navigator.clipboard.writeText(text);
  showToast("Full transcript copied to clipboard!");
});

copyDescBtn.addEventListener("click", () => {
  if (!currentVideoData || !currentVideoData.description) {
    showToast("No description to copy");
    return;
  }
  navigator.clipboard.writeText(currentVideoData.description);
  showToast("Description copied to clipboard!");
});
