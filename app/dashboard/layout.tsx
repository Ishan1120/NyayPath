import React from "react";
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <section className="dashboard-layout-wrapper h-full">
      {/* 
        This children prop is mandatory for Next.js layouts. 
        It renders your dashboard/page.tsx and sub-routes.
      */}
      {children}
    </section>
  );
}
