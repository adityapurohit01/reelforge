# Phase 5 Documentation: Storage & Instagram Reels Publishing

## 1. What Was Built

Phase 5 implements cloud storage ingestion and official Instagram Graph API Reels publishing for **ReelForge**.

### A. Storage Architecture (`src/reelforge/social/storage.py`, `src/reelforge/pipeline/stages/upload.py`)
Because Meta's Content Publishing API does not ingest raw binary video uploads directly from client machines, videos must be served from an accessible HTTPS URL:
1. **`StorageBackend` Interface**: Clean abstract base contract defining `upload(video_path, cover_path)` and `cleanup(object_keys)`.
2. **`R2Storage`**: Cloudflare R2 provider using S3-compatible protocol via `boto3`. Uploads video files under randomized UUID keys with explicit `Content-Type: video/mp4` headers and cover images with `image/jpeg`. Provides automatic cleanup of intermediate upload objects after publishing succeeds.
3. **`LocalMockStorage`**: Development and testing provider generating stable mock URLs without requiring cloud credentials.

### B. Instagram Content Publishing Engine (`src/reelforge/social/instagram.py`, `src/reelforge/pipeline/stages/publish.py`)
Built strictly to official Meta Instagram Graph API (v21.0) specifications:
1. **Pre-flight Quota Inspection**:
   - Queries `GET /{ig-user-id}/content_publishing_limit`.
   - Tracks 24-hour quota usage against the standard 50 API posts limit.
2. **Container-Based Publishing Protocol**:
   - Step 1: Initialize container via `POST /{ig-user-id}/media` with `media_type="REELS"`, `video_url`, `caption`, `share_to_feed="true"`, and optional `cover_url`.
   - Step 2: Poll container status via `GET /{container-id}?fields=status_code,status` with exponential backoff (5s up to 30s intervals) until `FINISHED`.
   - Step 3: Publish via `POST /{ig-user-id}/media_publish` with `creation_id`.
   - Step 4: Fetch verified public permalink via `GET /{media-id}?fields=permalink`.
3. **Idempotency & Duplicate Publishing Protection**:
   - Queries the SQLite `publish_log` table before initiating any network action.
   - If a video is already marked `status="PUBLISHED"`, the publisher immediately short-circuits, preventing costly accidental double-posts.
   - If an un-published container was already initialized for a run, the existing `container_id` is resumed rather than creating duplicate containers.
4. **Token Lifecycle Management**:
   - Implements `refresh_long_lived_token()` via `https://graph.instagram.com/refresh_access_token` (`grant_type="ig_refresh_token"`) with fallback to Facebook exchange token endpoint.
5. **Dry-Run Mode**:
   - Supports `--dry-run` flag which exercises all pipeline logic up to the final publish call, emitting a structured mock publication payload.

### C. Founder Setup Documentation
Created `docs/INSTAGRAM_SETUP.md` with step-by-step guidance on setting up a Meta Developer App in Business mode, configuring App Roles for tester permissions without App Review, and obtaining a 60-day long-lived token.

---

## 2. How It Was Verified

Acceptance checks were verified in `tests/integration/test_phase5_storage_instagram.py`:
- **Storage Lifecycle**: Confirmed `LocalMockStorage` creates valid asset URLs and cleans up keys.
- **End-to-End Publishing**: Verified full 3-step publishing flow with `respx` mocking Meta API endpoints, verifying that `PublishLog` receives status `PUBLISHED` with valid `media_id` and `permalink`.
- **Idempotency**: Pre-populated DB with existing published video; second call confirmed to return `already_published: True` with 0 HTTP calls.
- **Error Handling**: Simulated Meta container processing `ERROR` status; verified that `InstagramAPIError` is raised and database logs `FAILED_ERROR`.
- **Token Refresh**: Verified token refresh endpoint parsing and renewal.
- **Dry Run**: Verified dry-run execution returns preview URLs safely.
- **Execution Result**:
  `tests/integration/test_phase5_storage_instagram.py` passed 6/6 tests in 1.85s.

---

## 3. What Is Known to Be Weak / Limits

1. **Meta API Credentials**:
   Real publishing requires valid `IG_USER_ID` and `IG_ACCESS_TOKEN` in `.env`. Until provided by the founder, tests run using the verified `respx` HTTP mock suite or `--dry-run`.
2. **Video Processing Latency**:
   On Meta's production servers, Reel video ingestion typically takes 15-45 seconds for a 30s video, but can spike during infrastructure degraded states. The exponential backoff polling mechanism gracefully waits up to 10 minutes before timing out.
