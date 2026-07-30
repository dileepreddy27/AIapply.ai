import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIapply.ai",
  description: "Role-based job matching with resume RAG, auth, and payments"
};

// Restore the saved theme before paint to avoid a flash of the default theme.
// The theme toggle now lives inside the dashboard (post-login) only.
const themeInitScript = `(function(){try{var d=document.documentElement;if(localStorage.getItem('aiapply-theme')==='bw'){d.setAttribute('data-theme','bw');}}catch(e){}})();`;

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
