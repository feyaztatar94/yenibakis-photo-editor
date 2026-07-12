import { NextResponse } from "next/server";
import {
  authCredentials,
  COOKIE_NAME,
  createSessionToken,
  isAuthConfigured,
  SESSION_SECONDS,
} from "../../auth.server";

export async function POST(request: Request) {
  if (!isAuthConfigured()) {
    return NextResponse.json({ ok: false, message: "Giriş ayarları yapılandırılmamış." }, { status: 500 });
  }

  const contentType = request.headers.get("content-type") ?? "";
  const input = contentType.includes("application/json")
    ? (await request.json()) as { username?: string; password?: string }
    : (Object.fromEntries((await request.formData()).entries()) as { username?: string; password?: string });
  const expected = authCredentials();

  if (input.username !== expected.username || input.password !== expected.password) {
    return NextResponse.json({ ok: false, message: "Kullanıcı adı veya şifre hatalı." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(COOKIE_NAME, await createSessionToken(), {
    httpOnly: true,
    sameSite: "lax",
    secure: new URL(request.url).protocol === "https:",
    path: "/",
    maxAge: SESSION_SECONDS,
  });
  return response;
}
