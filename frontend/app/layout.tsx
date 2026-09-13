import "./globals.css";
import React from "react";

export const metadata = {
  title: "TrueLock | Forensic Accounting Intelligence",
  description: "Autonomous, bounded forensic auditor with Google Gemini function calling.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
