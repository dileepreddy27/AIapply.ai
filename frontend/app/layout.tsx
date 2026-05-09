import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIapply.ai",
  description: "Role-based job matching with resume RAG, auth, and payments"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
