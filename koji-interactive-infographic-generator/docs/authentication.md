# Standalone Supabase authentication

The hosted Studio requires sign-in before cloud jobs and history are available. Local mode (no Studio URL) and embedding with an existing access token remain supported.

Sign-in and signup have separate pages at `/signin` and `/signup`. Password assistance uses `/forgot-password`, `/verify-email`, and `/reset-password`. Browser navigation works between pages, and authenticated users return to the Studio.

## Implemented flow

- Supabase JavaScript SDK handles email/password sign-in, signup, confirmation, resending confirmation, password reset, session persistence and token refresh.
- Signup stores the display name in user metadata. Confirmation-enabled signup shows the verification screen; it does not create a signed-in session prematurely.
- Email links return to `/auth/callback`. Recovery links show a new-password form. Successful password updates sign this device out and request sign-in with the new password.
- Logout is scoped to this device. Other components using the same Supabase project are unaffected.
- The EC2 API verifies bearer tokens with the same project's Auth user endpoint. Owner IDs come from verified identity, never from client fields. Jobs, conversations and private assets keep their existing owner checks.
- `GET /studio/account` returns only ID, email, display name and email-confirmed status after token verification. The backend never receives signup/sign-in passwords.

## Existing project configuration

1. In Supabase **Authentication → Sign In / Providers → Email**, enable email/password signup and keep email confirmation enabled. Changing a shared provider setting affects every component; coordinate shared settings with the team.
2. In **Authentication → URL Configuration → Redirect URLs**, add:
   - `https://koji-studio.vercel.app/auth/callback`
   - `http://localhost:8081/auth/callback`
   - `http://localhost:8091/auth/callback`
   Preserve existing redirect entries and the shared project's Site URL.
3. Keep the default confirmation and reset templates using Supabase's confirmation URL. If a custom template hardcodes the shared Site URL, update it to respect the requested redirect destination.
4. Configure custom SMTP for verification and password-reset delivery to normal users. Supabase's built-in sender is restricted to project team addresses and low rate limits. Do not disable email confirmation merely to work around email delivery.
5. Frontend needs only `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` and `EXPO_PUBLIC_STUDIO_API_URL`. Use the existing project. Service-role keys and database URLs belong only in the backend environment.

Official setup references: [Redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls), [custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp).

## Update the currently running deployments

These commands match the manually configured EC2 path and systemd services. They do not replace the live backend environment.

**Windows PowerShell, repository root:**

```powershell
scp -i "$env:USERPROFILE\Downloads\koji-studio-key.pem" ".\koji-interactive-infographic-generator\backend\studio\main.py" ubuntu@54.224.186.62:/home/ubuntu/koji/backend/studio/main.py
```

**EC2 Ubuntu SSH terminal:**

```bash
sudo systemctl restart koji-api.service
curl -sS https://koji-studio-api.duckdns.org/ready
```

No database migration or new backend dependency is required by this authentication change.

**Windows PowerShell, component frontend directory:**

```powershell
npm run build:web -- --clear
py ..\ci\pack_vercel.py
npx vercel deploy --prebuilt --prod
```

## Release verification

Create a test account, follow its confirmation link, sign in, reload the page, inspect cloud history, and sign out. Try an incorrect password and ensure the form shows an error. Request a reset link, follow it, update the password, then sign in with the new password. Check narrow-screen layout. Test another account's history is inaccessible. Browser mock tests cannot establish real email delivery; verify that using the configured project's SMTP.

## Deployment status (2026-10-08)

The frontend was deployed to the existing Vercel production project and the API update was uploaded to EC2. HTTPS readiness returned OK; unsigned account requests return 401. The three redirect URLs above were saved with user approval, preserving the shared Site URL. Custom SMTP is currently disabled in this Supabase project; real public signup/reset email delivery still needs an SMTP provider. Local mock checks covered signup confirmation, resending, reset requests, recovery-link routing, login, reload persistence and logout; password-update logic and backend ownership were unit tested.

## Gmail SMTP for a small demo

Turn on Google 2-Step Verification, then create a dedicated App Password named learnX Supabase. The account owner must generate the credential and paste it directly into the Supabase SMTP password field; never put it in chat, frontend variables or repository files.

In Authentication → Emails → SMTP Settings, enable custom SMTP and use smtp.gmail.com, port 587, the Gmail address as both SMTP username and sender address, the App Password (not the normal Google password), and learnX as sender name. Save and test verification and password reset email delivery. These sender settings apply to the shared project. Gmail has sending limits; this setup is intended for a small demo.

References: [Google App Passwords](https://support.google.com/accounts/answer/185833), [Gmail SMTP](https://developers.google.com/workspace/gmail/imap/imap-smtp).

Verification controls appear on the signup confirmation screen or after an email_not_confirmed sign-in response. Editing the sign-in email clears that condition. Both password inputs use equal dimensions and independent eye toggles inside the fields.
