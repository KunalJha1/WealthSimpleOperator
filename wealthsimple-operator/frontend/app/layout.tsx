import "./globals.css";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";
import Sidebar from "../components/Sidebar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter"
});

export const metadata = {
  title: "Wealthsimple Operator Console",
  description: "Internal portfolio monitoring and triage console for wealth advisors.",
  icons: {
    icon: "/FAVICON.svg"
  }
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/FAVICON.svg" type="image/svg+xml" />
      </head>
      <body
        className={`${inter.variable} font-sans bg-white text-gray-900 antialiased`}
      >
        <div className="min-h-screen flex bg-ws-background">
          <Sidebar />
          <main className="flex-1 px-6 lg:px-10 py-8 max-w-[1600px] mx-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

