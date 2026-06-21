import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FairFlow Guardian",
  description: "Explainable AI trading safety layer for fairer market strategy decisions.",
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg"
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
