import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CV Screener | Soko Financial",
  description: "Aplikasi internal penyaringan dan pemeringkatan CV tim rekrutmen Soko Financial",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" className="h-full">
      <body className={`${inter.className} min-h-full bg-slate-950 text-slate-100 antialiased flex flex-col`}>
        {children}
      </body>
    </html>
  );
}
