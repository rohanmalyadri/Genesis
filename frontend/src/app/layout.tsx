import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SidebarNav } from "@/components/sidebar-nav";
import { SiteFooter } from "@/components/site-footer";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Genesis RAG",
  description:
    "Genesis RAG: agentic retrieval-augmented generation with hybrid search, sharding, PageRank authority and security guards. Made by Rohan Malyadri, Obscuron X Labs.",
  authors: [{ name: "Rohan Malyadri", url: "https://rohanmalyadri.in/" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} bg-background text-foreground`}>
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <SidebarNav />
            <div className="flex min-w-0 flex-1 flex-col">
              <main className="flex-1 overflow-y-auto bg-muted/10">{children}</main>
              <SiteFooter />
            </div>
          </div>
          <Toaster position="top-right" richColors closeButton />
        </Providers>
      </body>
    </html>
  );
}
