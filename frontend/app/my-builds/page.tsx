"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useUser } from "@clerk/nextjs";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pencil, Plus, Trash2 } from "lucide-react";
import {
  deleteBuild as deleteLocalBuild,
  listBuilds as listLocalBuilds,
  renameBuild as renameLocalBuild,
  sizeLabel,
  type StoredBuild,
} from "@/lib/builds";
import {
  deleteBuildRemote,
  listBuilds as listRemoteBuilds,
  renameBuildRemote,
  type BuildSummary,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Merge remote (API) and local (localStorage) build lists.
// Remote entries win on ID collision; local-only entries are appended.
// Sorted newest-first.
// ---------------------------------------------------------------------------
function mergeBuilds(remote: BuildSummary[], local: StoredBuild[]): StoredBuild[] {
  const remoteIds = new Set(remote.map((b) => b.id));

  // Convert remote summary → StoredBuild shape (indices omitted — not needed for list)
  const fromRemote: StoredBuild[] = remote.map((b) => ({
    id: b.id,
    title: b.title,
    createdAt: b.created_at,
    detail: (b.detail ?? "Medium") as StoredBuild["detail"],
    gridW: b.grid_w ?? 0,
    gridH: b.grid_h ?? 0,
    indices: [],                                // not loaded for list view
    thumbDataUrl: b.thumb_data_url ?? "",
    parts: [],                                  // not loaded for list view
  }));

  // Local-only builds (not yet synced / old pre-Phase-2 builds)
  const localOnly = local.filter((b) => !remoteIds.has(b.id));

  const merged = [...fromRemote, ...localOnly];
  return merged.sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );
}

export default function MyBuildsPage() {
  const router = useRouter();
  const { user, isLoaded } = useUser();

  const [builds, setBuilds] = useState<StoredBuild[] | null>(null);
  const [apiError, setApiError] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");

  // ---------------------------------------------------------------------------
  // Load builds: API primary, localStorage fallback / merge
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    async function load() {
      const local = listLocalBuilds();

      try {
        const remote = await listRemoteBuilds();
        if (cancelled) return;
        setBuilds(mergeBuilds(remote, local));
      } catch {
        // API unreachable or not signed in — fall back to localStorage only
        if (!cancelled) {
          setApiError(true);
          setBuilds(local);
        }
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  // ---------------------------------------------------------------------------
  // Rename
  // ---------------------------------------------------------------------------
  const startEdit = (e: React.MouseEvent, build: StoredBuild) => {
    e.preventDefault();
    e.stopPropagation();
    setEditingId(build.id);
    setEditingValue(build.title);
  };

  const commitEdit = async (id: string) => {
    const newTitle = editingValue.trim();
    setEditingId(null);
    if (!newTitle) return;

    // Optimistic update
    setBuilds((prev) =>
      (prev ?? []).map((b) => (b.id === id ? { ...b, title: newTitle } : b))
    );

    // Persist: try API first (may 404 if local-only build), then localStorage
    try {
      await renameBuildRemote(id, newTitle);
    } catch {
      // Local-only build — that's fine
    }
    renameLocalBuild(id, newTitle);
  };

  // ---------------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------------
  const handleDelete = async (e: React.MouseEvent, build: StoredBuild) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`Delete "${build.title}"? This cannot be undone.`)) return;

    // Optimistic removal
    setBuilds((prev) => (prev ?? []).filter((b) => b.id !== build.id));

    try {
      await deleteBuildRemote(build.id);
    } catch {
      // Local-only build
    }
    deleteLocalBuild(build.id);
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="max-w-7xl mx-auto px-6 py-12">
      <div className="mb-10 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-white tracking-tight">My Builds</h1>
          <p className="text-slate-400">
            {isLoaded && user?.firstName
              ? `Welcome back, ${user.firstName}. Here are your previous brick creations.`
              : "Your previous brick creations."}
          </p>
          {apiError && (
            <p className="text-xs text-amber-500/80">
              Showing locally cached builds — could not reach the server.
            </p>
          )}
        </div>
        <Link href="/create">
          <Button className="bg-indigo-600 hover:bg-indigo-500 text-white">
            <Plus className="w-4 h-4 mr-2" />
            New Build
          </Button>
        </Link>
      </div>

      {builds === null ? (
        <div className="text-slate-500 text-sm">Loading…</div>
      ) : builds.length === 0 ? (
        <div className="p-16 rounded-3xl border border-dashed border-slate-800 text-center space-y-6 bg-slate-900/20">
          <h2 className="text-2xl font-semibold text-white">No builds yet.</h2>
          <p className="text-slate-400 max-w-md mx-auto">
            Once you generate your first brick layout, it will show up here so you can
            revisit, download, or share it.
          </p>
          <Link href="/create">
            <Button className="px-8 py-6 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full font-medium shadow-lg shadow-indigo-500/20">
              Start Your First Build
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {builds.map((build, index) => (
            <motion.div
              key={build.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(index * 0.05, 0.4) }}
            >
              <Card
                onClick={() => router.push(`/build/${build.id}`)}
                className="group relative bg-slate-900/40 border-slate-800 overflow-hidden hover:border-indigo-500/50 transition-all duration-300 cursor-pointer"
              >
                <div className="aspect-[4/5] w-full bg-black/40 flex items-center justify-center relative overflow-hidden">
                  {build.thumbDataUrl ? (
                    <img
                      src={build.thumbDataUrl}
                      alt={build.title}
                      className="w-full h-full object-contain p-3 group-hover:scale-[1.02] transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-700 text-sm">
                      No preview
                    </div>
                  )}
                  <button
                    onClick={(e) => handleDelete(e, build)}
                    className="absolute top-2 right-2 p-2 bg-slate-900/80 hover:bg-red-500 text-slate-200 hover:text-white rounded-full transition shadow-lg backdrop-blur-sm"
                    aria-label={`Delete ${build.title}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="p-4 bg-slate-900/80 backdrop-blur-sm border-t border-slate-800">
                  <div className="flex justify-between items-start mb-2 gap-2">
                    {editingId === build.id ? (
                      <input
                        autoFocus
                        value={editingValue}
                        maxLength={60}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => setEditingValue(e.target.value)}
                        onBlur={() => commitEdit(build.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") commitEdit(build.id);
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        className="flex-1 min-w-0 bg-slate-800 text-white text-sm font-medium px-2 py-1 rounded border border-indigo-500 outline-none"
                      />
                    ) : (
                      <div className="flex items-center gap-1.5 min-w-0 flex-1">
                        <h3 className="text-white font-medium truncate">{build.title}</h3>
                        <button
                          onClick={(e) => startEdit(e, build)}
                          className="shrink-0 text-slate-500 hover:text-slate-200 transition"
                          aria-label="Rename build"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                    {build.gridW > 0 && (
                      <span className="text-[10px] border border-slate-700 text-slate-400 px-2 py-0.5 rounded-full uppercase font-semibold shrink-0">
                        {sizeLabel(build.gridW, build.gridH)}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-500">
                    {new Date(build.createdAt).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                    {build.gridW > 0 && ` · ${build.gridW}×${build.gridH}`}
                  </p>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
