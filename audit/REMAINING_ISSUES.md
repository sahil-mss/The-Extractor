# The Extractor — Remaining Issues, Limitations & Future Work

This document catalogues all items that could not be verified in the local test environment, upstream dependencies with known behavior characteristics, and recommended future enhancements for **The Extractor**.

---

## 1. Environment Limitations

### 1.1 Live Upstream Third-Party Endpoints
- **Constraint:** In accordance with the non-destructive testing mandate (Section 2.4), stress testing and heavy load testing did not target live external media hosts (YouTube, Vimeo, SoundCloud, etc.) or trigger bulk real-world media downloads.
- **Verification Performed:** Verified via comprehensive synthetic unit and integration tests using mocked `yt_dlp` extractors and synthetic payloads.
- **Next User Verification Step:** To verify specific niche extractors or live downloads, execute single manual downloads via the UI on representative test media.

### 1.2 Docker Multi-Node Deployment
- **Constraint:** The current audit was executed within the primary Windows 11 host environment (`win32`). A multi-container Docker Swarm or Kubernetes deployment was not provisioned during this cycle.
- **Verification Performed:** Hardened `Dockerfile` to create and run as a non-root `appuser` (UID 1000), added container `HEALTHCHECK` probing `/healthz`, and updated `docker-compose.yml` with mandatory `EXTRACTOR_API_KEY` validation, default loopback port publication (`127.0.0.1:8000:8000`), and safe optional configuration mounting.


---

## 2. Upstream Dependencies & External Factors

### 2.1 Upstream PyPI Version Check Latency
- **Finding Reference:** `FINDING-PERF-01`
- **Details:** The function `check_ytdlp_version()` in [downloader.py](file:///d:/Projects/The%20Extractor/downloader.py) queries the PyPI JSON API synchronously. While fine for single-user desktop settings, high-frequency queries to `/api/config` from multiple clients will experience network latency unless cached.
- **Recommendation:** Implement an in-memory TTL cache (e.g. 1-hour expiration) for upstream PyPI version lookups to decouple internal API latency from external network responsiveness.

### 2.2 Upstream yt-dlp Changes & Site Breakages
- **Details:** Video hosting platforms frequently modify their internal HTML layout, JavaScript obfuscation, or streaming protocols, which can cause `yt-dlp` extraction to fail until an updated release of `yt-dlp` is published.
- **Mitigation:** The application includes a built-in `check_ytdlp_version` routine and alert banner informing users when an updated `yt-dlp` wheel is available.

---

## 3. Recommended Future Enhancements

### 3.1 Server-Sent Events (SSE) / Bulk Task Streaming
- **Current State:** The frontend uses an adaptive polling mechanism with the `/api/tasks/bulk` endpoint, which is lightweight and robust.
- **Future Improvement:** For ultra-low latency updates in multi-client setups, a unidirectional Server-Sent Events (`/api/events`) connection could replace polling, reducing overall HTTP request volume.

### 3.2 Virtualized DOM for High-Volume History Lists
- **Current State:** The database uses server-side pagination with default page sizes of 20/50, keeping the DOM lightweight.
- **Future Improvement:** If a user chooses to view 500+ items per page, introducing virtual scrolling (e.g. rendering only visible table rows in viewport) will ensure 60fps scrolling on lower-end devices.

---

## 4. Prioritized Summary of Open Tasks

| Priority | Item | Description | Owner |
|---|---|---|---|
| **P3 (Low)** | PyPI TTL Cache | Cache PyPI response in `check_ytdlp_version` for 1 hour | Backend |
| **P3 (Low)** | UI Virtualization | Add virtualized scrolling if page size > 200 items | Frontend |
| **P4 (Info)** | Docker Compose Healthcheck | Add explicit container healthcheck in `docker-compose.yml` | DevOps |
