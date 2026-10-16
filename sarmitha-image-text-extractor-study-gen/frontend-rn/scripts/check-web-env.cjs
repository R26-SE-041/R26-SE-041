// Local web exports may use localhost; hosted builds need the public EC2 API.
if (process.env.VERCEL === "1") {
  let url;
  try {
    url = new URL(process.env.EXPO_PUBLIC_API_URL);
  } catch {
    throw new Error("Set EXPO_PUBLIC_API_URL in Vercel to the public HTTPS backend URL.");
  }
  if (url.protocol !== "https:" || ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    throw new Error("EXPO_PUBLIC_API_URL must point to the public HTTPS backend.");
  }
}
