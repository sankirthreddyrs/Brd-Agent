import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { Card } from "@/components/brd/Panels";

export const Route = createFileRoute("/support")({
  head: () => ({
    meta: [
      { title: "Support — BRD Agent" },
      { name: "description", content: "Support and feedback for the BRD Agent platform." },
      { property: "og:title", content: "Support — BRD Agent" },
      { property: "og:description", content: "Support and feedback for the BRD Agent platform." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <div className="space-y-3">
      <h1 className="text-[18px] font-semibold">Support</h1>
      <Card className="max-w-lg space-y-3 p-5">
        <textarea placeholder="Describe your issue…" className="h-28 w-full rounded-md border border-input bg-card p-3 text-[13px]" />
        <button onClick={() => toast.success("Message sent to support")} className="rounded-md bg-primary px-4 py-2 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90">Send message</button>
      </Card>
    </div>
  );
}
