# New common Supabase Auth project

The common frontend uses a new Supabase project for signup, login, email verification and password recovery. The four component databases stay in their existing projects/stores. The app already supports project configuration through its environment variables; it does not need a second login implementation.

## Dashboard configuration

1. Create a project, for example `BioLearnX Common Auth`, in Supabase. Keep its database password private.
2. Enable email/password authentication and user signup. Keep email confirmation enabled for real users.
3. Configure the development Site URL and redirect allowlist as `http://localhost:8085`. Add the deployed common app origin when hosting, and make that the production Site URL.
4. Configure custom SMTP for signup confirmation and password reset emails to student addresses. The default mail service is restricted to project team members.
5. Obtain the project URL and public publishable key or legacy anon key. Set these in `.env.local`, preserving existing backend API variables:

```dotenv
EXPO_PUBLIC_SUPABASE_URL=https://YOUR_NEW_PROJECT.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=YOUR_PUBLIC_PUBLISHABLE_OR_ANON_KEY
```

The variable name is unchanged even when using a publishable key. Never put a secret/service-role key, database password or signing secret in the frontend.

Restart `npm.cmd run web` after updating the environment. Test signup, email confirmation, login and password recovery. Accounts appear under Authentication → Users; a custom users table is not required for login. The SDK stores sessions under a project-specific key, separate from original frontend sessions.

## Integration boundary

Frontend login with the new project and authenticated access to existing backends are separate integration steps. Existing backend configurations currently trust their original Supabase projects:

- Audio locally verifies HS256 tokens against its original project's secret.
- Visual memory authenticates through its configured project's `/auth/v1/user` endpoint.
- Quiz and OCR currently lack server-side ownership enforcement.

Do not replace existing backend database credentials or signing secrets with the new project's values: this could break original frontends or redirect component data to another database.

To support both frontend types, add verification for the new common Auth issuer while retaining verification of original issuers, using strict issuer/audience checks. Validate the new project's actual signing algorithm rather than assuming HS256. Keep storage credentials unchanged. Scope identities by issuer and subject so old/new accounts cannot accidentally share another learner's data. Any linking of an old account to a common account must be explicit and verified.

This frontend configuration does not perform that backend integration, account linking or a data migration. Until those steps are completed, new-project login can work while authenticated Audio/Visual requests are rejected.

## Official references

- [Password authentication](https://supabase.com/docs/guides/auth/passwords)
- [API keys](https://supabase.com/docs/guides/getting-started/api-keys)
- [Redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls)
- [Custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp)
