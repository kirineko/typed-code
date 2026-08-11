import { realpath, stat } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";

import type { SessionSummary } from "@typed-code/sdk";

export interface WorkspaceIdentity {
  canonicalPath: string;
  displayPath: string;
}

export interface ProjectSessionGroup {
  workspacePath: string;
  label: string;
  sessions: SessionSummary[];
}

export async function normalizeWorkspace(path: string): Promise<WorkspaceIdentity> {
  const canonicalPath = await realpath(resolve(path));
  const info = await stat(canonicalPath);
  if (!info.isDirectory()) {
    throw new Error(`workspace must be a directory: ${path}`);
  }
  return { canonicalPath, displayPath: canonicalPath };
}

export function sessionsForWorkspace(
  sessions: readonly SessionSummary[],
  workspacePath: string,
): SessionSummary[] {
  return sortSessions(
    sessions.filter((session) => session.workspace_path === workspacePath),
  );
}

export function groupSessionsByWorkspace(
  sessions: readonly SessionSummary[],
): ProjectSessionGroup[] {
  const grouped = new Map<string, SessionSummary[]>();
  for (const session of sessions) {
    const group = grouped.get(session.workspace_path);
    if (group) {
      group.push(session);
    } else {
      grouped.set(session.workspace_path, [session]);
    }
  }

  const basenameCounts = new Map<string, number>();
  for (const workspacePath of grouped.keys()) {
    const name = basename(workspacePath) || workspacePath;
    basenameCounts.set(name, (basenameCounts.get(name) ?? 0) + 1);
  }

  return [...grouped.entries()]
    .map(([workspacePath, projectSessions]) => {
      const name = basename(workspacePath) || workspacePath;
      const label =
        (basenameCounts.get(name) ?? 0) > 1
          ? `${name} — ${dirname(workspacePath)}`
          : name;
      return {
        workspacePath,
        label,
        sessions: sortSessions(projectSessions),
      };
    })
    .sort(
      (left, right) =>
        left.label.localeCompare(right.label) ||
        left.workspacePath.localeCompare(right.workspacePath),
    );
}

function sortSessions(sessions: readonly SessionSummary[]): SessionSummary[] {
  return [...sessions].sort(
    (left, right) =>
      right.updated_at.localeCompare(left.updated_at) ||
      left.session_id.localeCompare(right.session_id),
  );
}
