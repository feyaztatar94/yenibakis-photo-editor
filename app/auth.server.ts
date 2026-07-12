const COOKIE_NAME = "yb_editor_session";
const SESSION_SECONDS = 60 * 60 * 8;

function credentials() {
  return {
    username: process.env.EDITOR_USERNAME?.trim() ?? "",
    password: process.env.EDITOR_PASSWORD ?? "",
    secret: process.env.AUTH_SECRET ?? "",
  };
}

function bytesToHex(bytes: ArrayBuffer) {
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function signature(payload: string, secret: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return bytesToHex(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)));
}

export function authCredentials() {
  return credentials();
}

export function isAuthConfigured() {
  const { username, password, secret } = credentials();
  return Boolean(username && password && secret.length >= 32);
}

export async function createSessionToken() {
  const { username, secret } = credentials();
  if (!isAuthConfigured()) return "";
  const expiresAt = Math.floor(Date.now() / 1000) + SESSION_SECONDS;
  const payload = `${username}.${expiresAt}`;
  return `${payload}.${await signature(payload, secret)}`;
}

export async function isValidSession(token?: string) {
  if (!token || !isAuthConfigured()) return false;
  const [username, expiresText, suppliedSignature, ...rest] = token.split(".");
  if (rest.length || !username || !expiresText || !suppliedSignature) return false;
  const { username: expectedUsername, secret } = credentials();
  const expiresAt = Number(expiresText);
  if (username !== expectedUsername || !Number.isFinite(expiresAt) || expiresAt <= Date.now() / 1000) return false;
  const expectedSignature = await signature(`${username}.${expiresText}`, secret);
  if (expectedSignature.length !== suppliedSignature.length) return false;
  let difference = 0;
  for (let index = 0; index < expectedSignature.length; index += 1) {
    difference |= expectedSignature.charCodeAt(index) ^ suppliedSignature.charCodeAt(index);
  }
  return difference === 0;
}

export { COOKIE_NAME, SESSION_SECONDS };
