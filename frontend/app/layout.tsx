import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SidebarProvider } from "./components/SidebarProvider";
import LayoutContent from "./components/LayoutContent";
import { LanguageProvider } from "./contexts/LanguageContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { DomainProvider } from "./contexts/DomainContext";
import { AuthProvider } from "./contexts/AuthContext";
import { ToastProvider } from "./components/ui/Toast";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "UKIP — Universal Knowledge Intelligence Platform",
  description: "Ingest, harmonize, enrich, analyze, and deliver high-value knowledge for decision-making across science, health, business, and humanities domains.",
};

// Inline script to set dark class before first paint to prevent flash
const themeScript = `
(function() {
  try {
    var theme = localStorage.getItem('app_theme');
    if (theme === 'dark' || (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark');
    }
  } catch(e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        <ThemeProvider>
          <AuthProvider>
            <LanguageProvider>
              <DomainProvider>
                <SidebarProvider>
                  <ToastProvider>
                    <LayoutContent>{children}</LayoutContent>
                  </ToastProvider>
                </SidebarProvider>
              </DomainProvider>
            </LanguageProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
