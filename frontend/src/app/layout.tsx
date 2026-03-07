import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CatoCode — Autonomous Code Maintainer",
  description: "AI-powered autonomous GitHub repository maintenance",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-surface-0 text-gray-200 min-h-screen antialiased">
        <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
          <div className="absolute -top-[40%] -left-[20%] w-[60%] h-[60%] rounded-full bg-accent/5 blur-[120px]" />
          <div className="absolute -bottom-[30%] -right-[20%] w-[50%] h-[50%] rounded-full bg-purple-600/5 blur-[120px]" />
        </div>
        {children}
      </body>
    </html>
  );
}
