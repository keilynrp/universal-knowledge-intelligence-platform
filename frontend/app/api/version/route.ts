import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET() {
  const version = process.env.NEXT_PUBLIC_APP_VERSION || process.env.UKIP_APP_VERSION || "local";

  return NextResponse.json(
    {
      app: "ukip-frontend",
      version,
      generatedAt: new Date().toISOString(),
    },
    {
      headers: {
        "Cache-Control": "no-store, max-age=0, must-revalidate",
        "X-UKIP-Build": version,
      },
    },
  );
}
