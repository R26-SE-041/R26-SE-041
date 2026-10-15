type SessionResult = { data: { session: { access_token: string } | null }; error: unknown };
type SessionAuth = { getSession: () => Promise<SessionResult>; refreshSession: () => Promise<SessionResult> };
export class SessionConnectionError extends Error {}

// Share one refresh when several requests discover an expired session together.
export function createSessionTokenProvider(auth: SessionAuth) {
  let refreshing: Promise<string> | undefined;
  async function read(force: boolean) {
    const { data, error } = await (force ? auth.refreshSession() : auth.getSession());
    if (error && typeof error === "object" && ("status" in error && (error.status === 0 || Number(error.status) >= 500) ||
      "name" in error && error.name === "AuthRetryableFetchError")) {
      throw new SessionConnectionError("Unable to refresh your session. Check your connection and retry.");
    }
    if (error || !data.session?.access_token) throw new Error("Session expired. Please sign in again.");
    return data.session.access_token;
  }
  return (force = false): Promise<string> => {
    if (!force) return refreshing || read(false);
    if (!refreshing) refreshing = read(true).finally(() => { refreshing = undefined; });
    return refreshing;
  };
}
