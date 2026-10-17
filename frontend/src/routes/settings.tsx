import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { Card } from "@/components/brd/Panels";
import { useApp } from "@/context/AppContext";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — BRD Agent" },
      { name: "description", content: "Workspace configuration and agent preferences in BRD Agent." },
      { property: "og:title", content: "Settings — BRD Agent" },
      { property: "og:description", content: "Workspace configuration and agent preferences in BRD Agent." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Page,
});

function Page() {
  const { user, activeProject } = useApp();

  return (
    <div className="space-y-3">
      <h1 className="text-[18px] font-semibold">Settings</h1>
      <Card className="max-w-lg space-y-3 p-5">
        <div>
          <label className="block text-[12px] text-muted-foreground">Workspace name</label>
          <input defaultValue="Enterprise BRD Studio" className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 text-[13px] text-foreground" />
        </div>
        <div>
          <label className="block text-[12px] text-muted-foreground">Default department</label>
          <input defaultValue="Product & Engineering" className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 text-[13px] text-foreground" />
        </div>
        <div>
          <label className="block text-[12px] text-muted-foreground">Notification email</label>
          <input defaultValue={user?.email || "analyst@enterprise.com"} className="mt-1 w-full rounded-md border border-input bg-card px-3 py-2 text-[13px] text-foreground" />
        </div>
        <div>
          <label className="block text-[12px] text-muted-foreground">FastAPI Backend Endpoint</label>
          <input defaultValue="http://localhost:8000" readOnly className="mt-1 w-full rounded-md border border-input bg-muted/40 px-3 py-2 text-[13px] text-muted-foreground cursor-not-allowed" />
        </div>
        <button onClick={() => toast.success("Settings saved")} className="rounded-md bg-primary px-4 py-2 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 cursor-pointer">Save changes</button>
      </Card>
    </div>
  );
}
