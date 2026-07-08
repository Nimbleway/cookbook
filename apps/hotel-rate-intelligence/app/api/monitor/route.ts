// CRUD for monitor configs (used in the alerting/cron mode)
import { NextRequest, NextResponse } from "next/server";
import { getMonitorConfigs, saveMonitorConfig, deleteMonitorConfig } from "@/lib/kv";
import { MonitorConfig } from "@/lib/types";
import { randomUUID } from "crypto";

export async function GET() {
  const configs = await getMonitorConfigs();
  return NextResponse.json(configs);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const config: MonitorConfig = {
    id: randomUUID(),
    userHotel: body.userHotel,
    competitors: body.competitors,
    threshold: Number(body.threshold ?? 10),
    windowDays: body.windowDays ?? 7,
    startDate: body.startDate ?? "",
    slackWebhookUrl: body.slackWebhookUrl ?? "",
    createdAt: new Date().toISOString(),
  };
  await saveMonitorConfig(config);
  return NextResponse.json(config, { status: 201 });
}

export async function DELETE(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  await deleteMonitorConfig(id);
  return NextResponse.json({ deleted: id });
}
