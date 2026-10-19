import Link from "next/link";
import {
  ArrowRight, Bot, Layers, Network, Search, ShieldCheck, Upload, Workflow,
} from "lucide-react";

const features = [
  { icon: Search, title: "Hybrid retrieval", text: "Dense vector search and BM25 keywords fused with Reciprocal Rank Fusion." },
  { icon: Workflow, title: "Corrective RAG", text: "Every retrieved chunk is graded; weak context triggers a rewrite or web search." },
  { icon: Layers, title: "Sharded index", text: "Documents are spread over 16 ChromaDB shards with consistent hashing." },
  { icon: Network, title: "PageRank authority", text: "Highly cited documents get a ranking boost from a citation graph." },
  { icon: ShieldCheck, title: "Security guards", text: "Input checks, content filtering and PII redaction on every answer." },
  { icon: Bot, title: "Multi-hop reasoning", text: "Complex questions are split into sub-questions and answered step by step." },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl space-y-12 p-8 md:p-12">
      <section className="space-y-6 pt-4">
        <span className="inline-block rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
          Agentic RAG platform
        </span>
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Genesis RAG</h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Upload your documents and ask questions. Genesis finds the right passages, checks them,
          and answers with citations you can click.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition hover:opacity-90"
          >
            <Upload className="h-4 w-4" /> Upload documents
          </Link>
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 rounded-xl border border-border px-5 py-3 text-sm font-medium transition hover:bg-muted"
          >
            Start chatting <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map(({ icon: Icon, title, text }) => (
          <div key={title} className="space-y-2 rounded-2xl border border-border bg-background p-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
              <Icon className="h-5 w-5 text-primary" />
            </div>
            <h2 className="font-semibold">{title}</h2>
            <p className="text-sm text-muted-foreground">{text}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
