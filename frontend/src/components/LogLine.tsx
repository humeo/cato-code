"use client";

import { useState } from "react";

interface LogLineProps {
  line: string;
  ts: string;
}

interface ParsedLog {
  type: string;
  [key: string]: unknown;
}

function tryParse(raw: string): ParsedLog | null {
  try {
    const obj = JSON.parse(raw);
    if (obj && typeof obj === "object" && obj.type) return obj as ParsedLog;
  } catch {
    // not JSON
  }
  return null;
}

function CollapsibleBlock({
  label,
  content,
  defaultOpen = false,
  accent = "text-gray-400",
}: {
  label: string;
  content: string;
  defaultOpen?: boolean;
  accent?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1 text-xs ${accent} hover:text-gray-200 transition-colors`}
      >
        <span className="w-3 text-center">{open ? "▾" : "▸"}</span>
        {label}
      </button>
      {open && (
        <pre className="mt-1 ml-4 text-xs text-gray-500 whitespace-pre-wrap break-words max-h-60 overflow-y-auto">
          {content}
        </pre>
      )}
    </div>
  );
}

export function LogLine({ line, ts }: LogLineProps) {
  const parsed = tryParse(line);
  const time = ts.substring(11, 19);

  if (!parsed) {
    return (
      <div className="flex gap-2 py-0.5">
        <span className="text-gray-600 text-xs shrink-0">{time}</span>
        <span className="text-gray-400 text-xs whitespace-pre-wrap break-words">
          {line}
        </span>
      </div>
    );
  }

  if (parsed.type === "assistant") {
    const text = (parsed.content as string) ?? (parsed.message as string) ?? "";
    return (
      <div className="flex gap-2 py-0.5">
        <span className="text-gray-600 text-xs shrink-0">{time}</span>
        <div className="text-xs text-gray-300 whitespace-pre-wrap break-words">
          {text}
        </div>
      </div>
    );
  }

  if (parsed.type === "tool_use") {
    const name = (parsed.name as string) ?? "tool";
    const input =
      typeof parsed.input === "string"
        ? parsed.input
        : JSON.stringify(parsed.input, null, 2);
    return (
      <div className="flex gap-2 py-0.5">
        <span className="text-gray-600 text-xs shrink-0">{time}</span>
        <CollapsibleBlock
          label={`tool: ${name}`}
          content={input}
          accent="text-blue-400"
        />
      </div>
    );
  }

  if (parsed.type === "tool_result") {
    const output =
      typeof parsed.output === "string"
        ? parsed.output
        : JSON.stringify(parsed.output, null, 2);
    return (
      <div className="flex gap-2 py-0.5">
        <span className="text-gray-600 text-xs shrink-0">{time}</span>
        <CollapsibleBlock
          label="result"
          content={output}
          accent="text-gray-500"
        />
      </div>
    );
  }

  if (parsed.type === "result") {
    const cost = parsed.cost_usd as number | undefined;
    const summary = (parsed.summary as string) ?? "";
    return (
      <div className="flex gap-2 py-1 border-t border-border-subtle mt-1">
        <span className="text-gray-600 text-xs shrink-0">{time}</span>
        <div className="text-xs">
          <span className="text-emerald-400 font-medium">Done</span>
          {cost != null && (
            <span className="text-amber-400 ml-2">${cost.toFixed(4)}</span>
          )}
          {summary && (
            <p className="text-gray-400 mt-0.5">{summary}</p>
          )}
        </div>
      </div>
    );
  }

  // Fallback: show raw JSON
  return (
    <div className="flex gap-2 py-0.5">
      <span className="text-gray-600 text-xs shrink-0">{time}</span>
      <span className="text-gray-500 text-xs whitespace-pre-wrap break-words">
        {line}
      </span>
    </div>
  );
}
