import type { Metadata } from "next";
import "./globals.css";
import ThemeToggle from "./theme-toggle";

export const metadata: Metadata = {
  title: "AIapply.ai",
  description: "Role-based job matching with resume RAG, auth, and payments"
};

// Applies the saved theme before paint to avoid a flash of the default theme.
const themeInitScript = `(function(){try{var d=document.documentElement;var t=localStorage.getItem('aiapply-theme');if(t==='bw'){d.setAttribute('data-theme','bw');}var m=localStorage.getItem('aiapply-mode');d.setAttribute('data-mode',m==='dark'?'dark':'light');}catch(e){}})();`;

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
      <body>
        <ThemeToggle />
        {children}
      </body>
    </html>
  );
}
