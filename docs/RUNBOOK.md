# ReelForge Operations & Founder Runbook

This runbook covers daily operations, CLI commands, scheduling, monitoring, and error recovery for the **ReelForge** autonomous marketing video pipeline.

---

## 1. Quick Start & Daily Workflow

### 1.1 Verify System Health
Run the diagnostic doctor before starting production batches:
```powershell
.\.venv\Scripts\python.exe -m reelforge.cli doctor
```
Ensure all required components (Python, Node.js, FFmpeg, Ollama, Database) display `[green]PASSED[/green]`.

### 1.2 Generate Daily Video Batch
To generate today's videos and send them to Telegram for approval:
```powershell
.\.venv\Scripts\python.exe -m reelforge.cli run --n 1
```
*Note: The pipeline executes planning, profile generation, scriptwriting, audio synthesis, word alignment, Remotion video rendering, and QC gates, stopping in state `AWAITING_APPROVAL`.*

### 1.3 Review on Telegram
Check your whitelisted Telegram chat. You will receive:
- The rendered 1080x1920 MP4 video and cover image.
- Briefing with business profile, vertical, scenario, Remotion layout, and voice pairing.
- Automated QC gate report summary (Duration, Loudness, ASR Word Error Rate).
- Proposed Instagram caption and hashtags.
- Interactive action buttons: **Approve & Publish**, **Reject**, **Regenerate**, or **Edit Caption**.

---

## 2. CLI Command Reference

| Command | Description | Example |
| :--- | :--- | :--- |
| `doctor` | Toolchain diagnostics and credentials check | `reelforge doctor` |
| `plan` | Generate novelty plans without video creation | `reelforge plan --n 10 --dry-run` |
| `run` | Execute end-to-end pipeline (stops at approval) | `reelforge run --n 3 --preview` |
| `resume` | Resume an interrupted run from last valid stage | `reelforge resume run_abc123` |
| `approve` | Manually approve or reject a video from CLI | `reelforge approve run_abc123 -d APPROVE` |
| `publish` | Publish an approved video to Instagram Reels | `reelforge publish run_abc123 --dry-run` |
| `metrics` | Pull Instagram Reels insights & update bandit | `reelforge metrics` |
| `report` | View diversity coverage or bandit performance | `reelforge report diversity --last 30` |
| `demo` | Render a personalized demo for a single client | `reelforge demo -b prospect.json` |

---

## 3. Automated Scheduling (Windows Task Scheduler)

To run ReelForge automatically every morning at 09:00 AM on Windows:

Open PowerShell as Administrator and run:
```powershell
$Action = New-ScheduledTaskAction `
    -Execute "D:\Desktop\video automation\.venv\Scripts\python.exe" `
    -Argument "-m reelforge.cli run --n 1" `
    -WorkingDirectory "D:\Desktop\video automation"

$Trigger = New-ScheduledTaskTrigger -Daily -At 9:00am

Register-ScheduledTask `
    -TaskName "ReelForge_Daily_Video" `
    -Action $Action `
    -Trigger $Trigger `
    -Description "Autonomous daily marketing video generation for Vocalis AI"
```

To schedule the periodic metrics collection job (runs daily at 11:00 PM):
```powershell
$ActionMetrics = New-ScheduledTaskAction `
    -Execute "D:\Desktop\video automation\.venv\Scripts\python.exe" `
    -Argument "-m reelforge.cli metrics" `
    -WorkingDirectory "D:\Desktop\video automation"

$TriggerMetrics = New-ScheduledTaskTrigger -Daily -At 11:00pm

Register-ScheduledTask `
    -TaskName "ReelForge_Daily_Metrics" `
    -Action $ActionMetrics `
    -Trigger $TriggerMetrics `
    -Description "Collect Instagram Insights and update Thompson Bandit priors"
```

---

## 4. Troubleshooting & Error Recovery

### 4.1 Resuming an Interrupted Run
If a run was interrupted (e.g. laptop closed or power outage during rendering):
1. Identify the failed or stalled `run_id` from `runs/` or the SQLite DB.
2. Run:
   ```powershell
   reelforge resume <run_id>
   ```
3. ReelForge checks previously completed stage artifacts (`dialogue.json`, `mix.wav`, `words.json`) and continues from the next pending stage without repeating expensive LLM or TTS calls.

### 4.2 Handling QC Gate Failures
If a run fails with `FAILED_QC`:
- Inspect `runs/<run_id>/qc_report.json` to view the exact violation:
  - `Loudness outside target`: Check input music bed volume.
  - `Claims violation`: Check whether dialogue included prohibited guarantees or statistics.
  - `ASR Word Error Rate > 15%`: Check TTS audio clarity or spelling.
- You can regenerate with a fresh seed:
  ```powershell
  reelforge generate --run-id <run_id> --force
  ```

### 4.3 Disk Hygiene Policy
ReelForge automatically retains full stage artifacts (WAV turns, intermediate JSON, props) for the **last 30 runs**.
To purge older raw audio files while keeping final MP4s and manifests:
```powershell
# Retention cleanup command
powershell -Command "Get-ChildItem runs/ -Directory | Sort-Object CreationTime -Descending | Select-Object -Skip 30 | ForEach-Object { Remove-Item (Join-Path $_.FullName 'turn_*.wav') -Force -ErrorAction SilentlyContinue }"
```
