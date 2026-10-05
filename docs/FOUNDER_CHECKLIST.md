# ReelForge Founder Setup Checklist

This document details the external accounts, credentials, and configuration steps needed to move ReelForge from offline/dry-run mode into live, fully automated production.

Follow these 3 setup steps in the exact order listed below.

---

## Step 1: Telegram Approval Bot (Est. time: 3 mins)

The Telegram bot sends generated videos directly to your phone for approval before anything is published.

1. **Create Bot:**
   - Open Telegram and search for `@BotFather`.
   - Send `/newbot`.
   - Choose a name (e.g. `Vocalis Video Reviewer`) and a username ending in `bot` (e.g. `vocalis_review_bot`).
   - Copy the HTTP API token provided by BotFather.
2. **Find Your Chat ID:**
   - Search for `@userinfobot` on Telegram and send `/start`.
   - Copy your numeric `Id` (e.g. `123456789`).
3. **Add to `.env`:**
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
   TELEGRAM_ALLOWED_CHAT_IDS=[123456789]
   ```

---

## Step 2: Meta App & Instagram Professional Account (Est. time: 10 mins)

Required for publishing Instagram Reels via the official Instagram Graph API.

1. **Prerequisites:**
   - Ensure your Instagram account is switched to **Professional** (Creator or Business).
   - Ensure it is linked to a **Facebook Page** (under Instagram Settings > Creator Tools > Connect Facebook Page).
2. **Meta Developer App:**
   - Go to [developers.facebook.com](https://developers.facebook.com) > **Create App** > Type: **Business**.
   - Add products: **Instagram Graph API** and **Facebook Login for Business**.
3. **Roles (Development Mode):**
   - Go to **App Roles** > **Roles** > Add your Instagram/Facebook account as an **App Tester** or **Developer**. (This bypasses public Meta App Review!).
4. **Generate 60-Day Long-Lived Token:**
   - Follow the detailed steps in [INSTAGRAM_SETUP.md](file:///D:/Desktop/video%20automation/docs/INSTAGRAM_SETUP.md) using the Meta Graph API Explorer.
5. **Add to `.env`:**
   ```env
   IG_USER_ID=17841400000000000
   IG_ACCESS_TOKEN=EAAB...
   META_APP_ID=123456789012345
   META_APP_SECRET=abcdef1234567890abcdef1234567890
   GRAPH_API_VERSION=v21.0
   ```

---

## Step 3: Cloudflare R2 Storage (Est. time: 5 mins)

Instagram requires public HTTPS URLs to download Reel video files. Cloudflare R2 provides S3-compatible storage with **zero egress bandwidth fees**.

1. **Create Bucket:**
   - Log into [Cloudflare Dashboard](https://dash.cloudflare.com/) > **R2 Object Storage**.
   - Click **Create bucket** > Name it: `reelforge-media`.
2. **Enable Public Access or Custom Domain:**
   - In your bucket settings, go to **Settings** > **Public access** > Connect a custom domain (e.g. `media.vocalis.ai`) or enable the R2 managed `r2.dev` public subdomain.
3. **Generate API Token:**
   - Go to **R2** > **Manage R2 API Tokens** > **Create API Token**.
   - Permissions: **Object Read & Write**.
   - Copy the `Access Key ID`, `Secret Access Key`, and your `Account ID`.
4. **Add to `.env`:**
   ```env
   R2_ACCOUNT_ID=your_cloudflare_account_id
   R2_ACCESS_KEY_ID=your_r2_access_key
   R2_SECRET_ACCESS_KEY=your_r2_secret_key
   R2_BUCKET=reelforge-media
   R2_PUBLIC_BASE_URL=https://media.vocalis.ai
   ```

---

## Step 4: Verification

Run the diagnostics doctor:
```powershell
reelforge doctor
```
All rows will now display `[green]PASSED[/green]` / `[green]CONFIGURED[/green]`.
You are ready to run:
```powershell
reelforge run --n 1
```
