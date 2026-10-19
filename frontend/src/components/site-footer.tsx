import { Heart } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="shrink-0 border-t border-border bg-background/80 px-4 py-2 text-center text-xs text-muted-foreground backdrop-blur">
      Made with{" "}
      <Heart className="mx-0.5 inline h-3.5 w-3.5 fill-red-500 align-[-2px] text-red-500" aria-label="love" /> by{" "}
      <span className="font-medium text-foreground">Rohan Malyadri</span> from{" "}
      <span className="font-medium text-foreground">Obscuron X Labs</span>
    </footer>
  );
}
