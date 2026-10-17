import { NextResponse } from "next/server";
import {
  SESSION_COOKIE_NAME,
  SESSION_MAX_AGE_SECONDS,
  signSession,
  verifyPassword,
} from "@/lib/auth";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const { password } = body as { password?: string };

    const expectedPassword = process.env.APP_PASSWORD;
    const sessionSecret = process.env.SESSION_SECRET;

    if (!expectedPassword || !sessionSecret) {
      return NextResponse.json(
        {
          success: false,
          error: "Konfigurasi server belum lengkap (APP_PASSWORD / SESSION_SECRET).",
        },
        { status: 500 }
      );
    }

    if (!password || typeof password !== "string") {
      return NextResponse.json(
        {
          success: false,
          error: "Password wajib diisi.",
        },
        { status: 400 }
      );
    }

    const isValid = await verifyPassword(password, expectedPassword);
    if (!isValid) {
      return NextResponse.json(
        {
          success: false,
          error: "Password salah. Silakan periksa kembali.",
        },
        { status: 401 }
      );
    }

    const token = await signSession(sessionSecret);

    const response = NextResponse.json({
      success: true,
      message: "Login berhasil.",
    });

    response.cookies.set({
      name: SESSION_COOKIE_NAME,
      value: token,
      httpOnly: true,
      sameSite: "strict",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: SESSION_MAX_AGE_SECONDS,
    });

    return response;
  } catch (err: unknown) {
    return NextResponse.json(
      {
        success: false,
        error: "Terjadi kesalahan internal pada server.",
      },
      { status: 500 }
    );
  }
}
