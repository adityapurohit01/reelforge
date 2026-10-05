# Instagram Graph API Setup Guide for Founder

This document provides a comprehensive, step-by-step guide to setting up your Meta Developer App, linking your Instagram Professional account, and generating a 60-day long-lived access token for **ReelForge** automated Reels publishing.

---

## 1. Prerequisites Checklist

Before creating the API integration, ensure you have:
1. An **Instagram Professional Account** (either **Business** or **Creator**). Personal accounts cannot publish via API.
2. A **Facebook Page** associated with your brand (required to link Meta permissions).
3. The Instagram account connected to your Facebook Page:
   - On Instagram: Go to **Settings & Privacy** > **Creator tools and controls** (or **Business**) > **Connect a Facebook Page**.
4. A **Meta Developer Account**: Register at [developers.facebook.com](https://developers.facebook.com).

---

## 2. Create the Meta Developer App

1. Go to the [Meta Developer App Dashboard](https://developers.facebook.com/apps).
2. Click **Create App**.
3. Select **Other** > Next > Choose **Business** as the app type.
4. Fill in:
   - **App Name:** `Vocalis AI Video Publisher` (or your company name).
   - **App Contact Email:** Your founder/tech email.
5. Click **Create App** and complete the security check.

---

## 3. Configure App Roles (Development Mode)

While your app is in **Development Mode** (before formal App Review):
1. In the left navigation menu, go to **App Roles** > **Roles**.
2. Click **Add People**.
3. Under **Testers** or **Developers**, add your personal Facebook / Instagram account.
4. Log into that account and accept the tester invitation.
*Note: Testers can publish to their own linked Instagram accounts without needing public Meta App Review.*

---

## 4. Add the Instagram Graph API Product

1. In the App Dashboard, click **Add Products to Your App**.
2. Find **Instagram Graph API** and click **Set Up**.
3. Also find **Facebook Login for Business** and click **Set Up**.

---

## 5. Required Permission Scopes

When generating tokens, request the following exact permissions:
- `instagram_business_basic`
- `instagram_business_content_publish`
- `pages_show_list`
- `pages_read_engagement`

---

## 6. How to Generate a 60-Day Long-Lived Access Token

### Step A: Generate Short-Lived User Token
1. Open the [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. In the top right:
   - **Meta App:** Select your created app.
   - **User or Page:** Select **User Token**.
3. In **Permissions**, add:
   - `instagram_business_basic`
   - `instagram_business_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
4. Click **Generate Access Token** and approve the Facebook login modal.

### Step B: Find Your Instagram Business Account ID
In the Graph API Explorer query box, run:
```http
GET me/accounts?fields=name,instagram_business_account{id,username}
```
In the JSON response, locate `instagram_business_account.id`. This is your `IG_USER_ID`.

### Step C: Exchange for a 60-Day Long-Lived Token
Run the following curl command in your terminal (or use the Access Token Debugger tool):
```bash
curl -X GET "https://graph.facebook.com/v21.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id=<YOUR_META_APP_ID>&\
client_secret=<YOUR_META_APP_SECRET>&\
fb_exchange_token=<SHORT_LIVED_ACCESS_TOKEN>"
```

The response returns:
```json
{
  "access_token": "EAA...",
  "token_type": "bearer",
  "expires_in": 5184000
}
```
`expires_in: 5184000` seconds equals **60 days**.

---

## 7. Adding Credentials to ReelForge

Open your `.env` file in the project root and populate the values:
```env
# Meta / Instagram Publishing
IG_USER_ID=17841400000000000
IG_ACCESS_TOKEN=EAA...
META_APP_ID=123456789012345
META_APP_SECRET=abcdef1234567890abcdef1234567890
GRAPH_API_VERSION=v21.0
```

---

## 8. Verifying Your Setup with ReelForge

Run the diagnostic tool:
```bash
reelforge doctor
```
Or test publishing in dry-run mode:
```bash
reelforge run --dry-run
```
ReelForge will verify the token, validate your remaining 24-hour publishing quota (typically 50 Reels/day), and confirm container generation without making public posts.
