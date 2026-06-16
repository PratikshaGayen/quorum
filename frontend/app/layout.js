import "./globals.css";

export const metadata = {
  title: "Quorum — Verifiable Decision Engine",
  description: "A jury of LLMs on one AMD Instinct GPU.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
