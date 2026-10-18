# AdaptiveIQ panel demonstration

Live app: https://nishy-adaptive-quiz.vercel.app

## Prepare your account

Create an account and confirm its email before the presentation. Finish one
five-question quiz so My quizzes has a real result to show. Keep the password
private. Open the app on desktop and check the mobile layout once.

**Email setup:** custom SMTP is needed for confirmation and reset emails to
arbitrary users. Supabase's default mailer only sends to project team members,
with a two-email-per-hour limit. Do not depend on repeated email requests
during the presentation until custom SMTP is configured.

## Five-minute sequence

1. **Personal account:** sign in and open My quizzes. Explain that each account
   has its own quiz library and uploaded documents.
2. **Saved progress:** show a completed quiz, its date, progress and score.
   Open View results to show feedback and learning recommendations.
3. **Find an attempt:** search by topic and use the Completed filter. Clear
   the search and return the filter to All progress.
4. **Safe deletion:** choose Move to bin. Show the confirmation, then open
   Recycle bin. Explain that answers and scores are preserved.
5. **Restore:** restore the quiz, return to My quizzes and reopen its results.
   The score and answers remain available.
6. **Account security:** open Account and demonstrate password validation.
   If changing the password, use the new password for your next sign-in.
7. **New practice:** start a new quiz from a focused Biology topic or uploaded
   study material. Keep the completed quiz available while generation runs.

If SMTP is configured, demonstrate Forgot password in a separate browser
window: request a link, open the latest email, set a new password, then sign in.
Recovery links are single-use; request a new one if an old link has expired.

## Implementation evidence

- Frontend: Vercel; API and graph checkpoints: EC2; accounts and assessment
  records: Supabase.
- API ownership checks reject requests for another account's quiz, results,
  documents and recycle-bin actions.
- Recycle bin uses soft deletion. There is no automatic purge.
- Automated checks cover authentication rejection, account isolation and
  restoration without losing progress. Disposable live tests exercise a full
  five-question quiz and real password recovery links without sending email.
