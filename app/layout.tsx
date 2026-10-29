import type { Metadata, Viewport } from "next";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://jan-adhikar.vercel.app";

export const viewport: Viewport = {
  themeColor: "#881337",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "NyayPath | RTI Filing & Legal Grievances Online",
    template: "%s | NyayPath",
  },
  description:
    "NyayPath is an autonomous legal assistant for Indian citizens. Simplify NyayPath RTI filing, draft consumer dispute notices, and resolve legal grievances instantly.",
  keywords: [
    "NyayPath",
    "NyayPath rti filing",
    "NyayPath Legal",
    "File RTI India NyayPath",
    "NyayPath consumer court draft",
    "Right to Information Act 2005",
    "Indian legal drafting AI",
    "Civic rights India",
  ],
  authors: [{ name: "NyayPath Civic Tech" }],
  creator: "NyayPath",
  publisher: "NyayPath",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "en_IN",
    url: siteUrl,
    title: "NyayPath | RTI Filing & Legal Grievances Online",
    description:
      "Transform civic issues into legally binding NyayPath RTI applications, consumer notices, and statutory appeals instantly.",
    siteName: "NyayPath",
    images: [
      {
        url: "/nyaypath-logo-v2.png",
        width: 1200,
        height: 630,
        alt: "NyayPath Legal Engine",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "NyayPath | Indian Civic & Legal Drafting Engine",
    description:
      "Draft court-ready RTI applications and legal grievance notices in minutes with NyayPath.",
    images: ["/nyaypath-logo-v2.png"],
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GSC_VERIFICATION || "YOUR_GOOGLE_VERIFICATION_CODE_HERE",
  },
  icons: {
    icon: "/favicon.png",
    apple: "/favicon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": ["WebApplication", "LegalService"],
    name: "NyayPath",
    alternateName: ["NyayPath", "NyayPath Legal", "NyayPath RTI"],
    url: siteUrl,
    applicationCategory: "LegalApplication",
    operatingSystem: "All",
    description:
      "NyayPath is an autonomous legal engine translating civic complaints into structured RTI applications and consumer notices under Indian law.",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "INR",
    },
    areaServed: {
      "@type": "Country",
      name: "India",
    },
    sameAs: [
      "https://jan-adhikar.vercel.app",
    ]
  };

  return (
    <html lang="en" className="h-full antialiased scroll-smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-full flex flex-col font-sans bg-slate-50 text-slate-900 selection:bg-court-maroon selection:text-white">
        {children}
      </body>
    </html>
  );
}
