import { ExperienceApp } from "@/components/experience-app";
import { liveReadyRetailers } from "@/lib/retailers";

export default function Home() {
  // Live Mode is available only when Nimble is fully configured. Otherwise the
  // app runs entirely on Demo data — the default, zero-config experience.
  const liveAvailable =
    process.env.FORCE_DEMO === "1"
      ? false
      : Boolean(process.env.NIMBLE_API_KEY) && liveReadyRetailers().length > 0;

  return (
    <ExperienceApp liveAvailable={liveAvailable} />
  );
}
