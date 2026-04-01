import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  // Pluggy OAuth callback placeholder
  const { searchParams } = new URL(request.url);
  const itemId = searchParams.get("itemId");

  if (!itemId) {
    return NextResponse.redirect(new URL("/settings?error=missing_item", request.url));
  }

  return NextResponse.redirect(new URL("/settings?connected=true", request.url));
}
