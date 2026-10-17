export const SESSION_COOKIE_NAME = "cv_session";
export const SESSION_MAX_AGE_SECONDS = 8 * 3600; // 8 jam (28800 detik)

/**
 * Membandingkan password yang diinput dengan expected password secara constant-time
 * menggunakan Web Crypto API (didukung di Edge Runtime, Node.js, dan Serverless).
 */
export async function verifyPassword(provided: string, expected: string): Promise<boolean> {
  if (!provided || !expected) return false;
  const enc = new TextEncoder();
  const hashProvided = await crypto.subtle.digest("SHA-256", enc.encode(provided));
  const hashExpected = await crypto.subtle.digest("SHA-256", enc.encode(expected));
  const bufA = new Uint8Array(hashProvided);
  const bufB = new Uint8Array(hashExpected);
  if (bufA.length !== bufB.length) return false;
  let diff = 0;
  for (let i = 0; i < bufA.length; i++) {
    diff |= bufA[i] ^ bufB[i];
  }
  return diff === 0;
}

/**
 * Menghasilkan token sesi bertanda tangan HMAC-SHA256.
 * Format: <timestamp>.<hex_hmac_signature>
 */
export async function signSession(secret: string): Promise<string> {
  if (!secret) {
    throw new Error("SESSION_SECRET belum dikonfigurasi di environment variable.");
  }
  const enc = new TextEncoder();
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signatureBuffer = await crypto.subtle.sign("HMAC", key, enc.encode(timestamp));
  const signature = Array.from(new Uint8Array(signatureBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return `${timestamp}.${signature}`;
}

/**
 * Memverifikasi integritas dan masa berlaku token sesi.
 */
export async function verifySession(
  token: string | undefined | null,
  secret: string,
  maxAgeSec: number = SESSION_MAX_AGE_SECONDS
): Promise<boolean> {
  if (!token || !secret) return false;
  const parts = token.split(".");
  if (parts.length !== 2) return false;

  const [timestampStr, signature] = parts;
  const timestamp = parseInt(timestampStr, 10);
  if (isNaN(timestamp)) return false;

  const now = Math.floor(Date.now() / 1000);
  // Cek apakah sudah kedaluwarsa atau timestamp di masa depan (toleransi 60 detik clock skew)
  if (now - timestamp > maxAgeSec || timestamp - now > 60) {
    return false;
  }

  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const expectedSigBuffer = await crypto.subtle.sign("HMAC", key, enc.encode(timestampStr));
  const expectedSignature = Array.from(new Uint8Array(expectedSigBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  if (signature.length !== expectedSignature.length) {
    return false;
  }

  let diff = 0;
  for (let i = 0; i < signature.length; i++) {
    diff |= signature.charCodeAt(i) ^ expectedSignature.charCodeAt(i);
  }
  return diff === 0;
}
