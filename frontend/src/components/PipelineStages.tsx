const STAGES = ["pending", "running", "done"] as const;

const STAGE_LABELS: Record<string, string> = {
  pending: "Pending",
  pending_approval: "Awaiting Approval",
  running: "Running",
  done: "Done",
  failed: "Failed",
};

interface PipelineStagesProps {
  stage: string;
  compact?: boolean;
}

export function PipelineStages({ stage, compact = false }: PipelineStagesProps) {
  const isFailed = stage === "failed";
  const isPendingApproval = stage === "pending_approval";

  // Map pipeline_stage to the step index (0-based)
  const activeIndex = isFailed
    ? 2 // terminal position
    : isPendingApproval
      ? 0
      : STAGES.indexOf(stage as (typeof STAGES)[number]);

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        {STAGES.map((s, i) => {
          const isCompleted = i < activeIndex;
          const isCurrent = i === activeIndex;
          const isFail = isCurrent && isFailed;

          return (
            <div
              key={s}
              className={`h-1.5 rounded-full transition-all ${
                compact ? "w-4" : "w-6"
              } ${
                isFail
                  ? "bg-red-400"
                  : isCompleted
                    ? "bg-accent"
                    : isCurrent
                      ? "bg-accent animate-pulse"
                      : "bg-gray-700"
              }`}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {STAGES.map((s, i) => {
        const isCompleted = i < activeIndex;
        const isCurrent = i === activeIndex;
        const isFail = isCurrent && isFailed;
        const label =
          isCurrent && isPendingApproval
            ? STAGE_LABELS.pending_approval
            : isCurrent && isFailed
              ? STAGE_LABELS.failed
              : STAGE_LABELS[s];

        return (
          <div key={s} className="flex items-center gap-2">
            {i > 0 && (
              <div
                className={`h-px w-6 ${
                  isCompleted ? "bg-accent" : "bg-gray-700"
                }`}
              />
            )}
            <div className="flex items-center gap-1.5">
              <div
                className={`w-2.5 h-2.5 rounded-full ${
                  isFail
                    ? "bg-red-400"
                    : isCompleted
                      ? "bg-accent"
                      : isCurrent
                        ? "bg-accent animate-pulse"
                        : "bg-gray-700"
                }`}
              />
              <span
                className={`text-xs ${
                  isFail
                    ? "text-red-400 font-medium"
                    : isCurrent
                      ? "text-gray-200 font-medium"
                      : isCompleted
                        ? "text-gray-400"
                        : "text-gray-600"
                }`}
              >
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
