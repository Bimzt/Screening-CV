import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME, verifySession } from "@/lib/auth";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const sessionSecret = process.env.SESSION_SECRET || "";

  // Lewati static assets Next.js dan favicon
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon.ico") ||
    pathname.startsWith("/images")
  ) {
    return NextResponse.next();
  }

  // Lewati route autentikasi
  if (
    pathname === "/auth/login" ||
    pathname === "/auth/logout"
  ) {
    return NextResponse.next();
  }

  const sessionCookie = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const isAuthenticated = sessionSecret
    ? await verifySession(sessionCookie, sessionSecret)
    : false;

  // Jika halaman login dibuka
  if (pathname === "/login") {
    if (isAuthenticated) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  // Jika belum login, redirect ke /login
  if (!isAuthenticated) {
    // Jika request ke /api dan belum login, kembalikan JSON 401
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        {
          status: "error",
          message: "Sesi tidak valid atau telah kedaluwarsa. Silakan login terlebih dahulu.",
        },
        { status: 401 }
      );
    }

    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
