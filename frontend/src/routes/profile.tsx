import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { Card } from "@/components/brd/Panels";
import { useApp } from "@/context/AppContext";
import { LogOut, ShieldCheck, Mail, Key } from "lucide-react";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Profile — BRD Agent" },
      { name: "description", content: "User profile and authentication settings in BRD Agent." },
      { property: "og:title", content: "Profile — BRD Agent" },
      { property: "og:description", content: "User profile and authentication settings in BRD Agent." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Page,
});

function Page() {
  const { user, signOut } = useApp();

  const email = user?.email || "anonymous@brdagent.com";
  const initials = email.slice(0, 2).toUpperCase();
  const userId = user?.id || "Unregistered";
  const createdAt = user?.created_at ? new Date(user.created_at).toLocaleDateString() : "Active";

  return (
    <div className="space-y-4 max-w-xl">
      <h1 className="text-[18px] font-semibold text-foreground">User Profile</h1>
      
      <Card className="flex flex-col gap-5 p-5">
        <div className="flex items-center gap-4">
          <span className="grid h-14 w-14 place-items-center rounded-full bg-primary/10 text-primary text-[18px] font-bold border border-primary/20">
            {initials}
          </span>
          <div className="min-w-0">
            <div className="font-semibold text-foreground truncate">{email}</div>
            <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground mt-0.5">
              <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
              <span>Supabase Authenticated</span>
            </div>
          </div>
        </div>

        <div className="border-t border-border pt-4 space-y-2.5 text-[12.5px]">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="flex items-center gap-1.5"><Mail className="h-3.5 w-3.5" /> Email</span>
            <span className="text-foreground font-mono">{email}</span>
          </div>
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="flex items-center gap-1.5"><Key className="h-3.5 w-3.5" /> Supabase UID</span>
            <span className="text-foreground font-mono text-[11px] truncate max-w-[240px]">{userId}</span>
          </div>
          <div className="flex items-center justify-between text-muted-foreground">
            <span>Member Since</span>
            <span className="text-foreground">{createdAt}</span>
          </div>
        </div>

        <div className="border-t border-border pt-4 flex items-center justify-between">
          <button
            onClick={() => toast.success("Profile preferences saved")}
            className="rounded-md border border-border px-3.5 py-1.5 text-[12px] font-medium hover:bg-muted text-foreground transition-colors"
          >
            Save Preferences
          </button>
          <button
            onClick={() => signOut()}
            className="flex items-center gap-1.5 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20 px-3.5 py-1.5 text-[12px] font-medium hover:bg-rose-500/20 transition-colors cursor-pointer"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign Out
          </button>
        </div>
      </Card>
    </div>
  );
}
