import { describe, expect, it } from "bun:test";

import { shouldUseHistoryBack } from "./navigation";

describe("shouldUseHistoryBack", () => {
  it("uses browser history when the user came from the dashboard in the same origin", () => {
    expect(
      shouldUseHistoryBack({
        historyLength: 3,
        referrer: "https://catocode.com/dashboard/activity/prev",
        origin: "https://catocode.com",
      })
    ).toBe(true);
  });

  it("falls back to dashboard when there is no same-origin history", () => {
    expect(
      shouldUseHistoryBack({
        historyLength: 1,
        referrer: "",
        origin: "https://catocode.com",
      })
    ).toBe(false);
    expect(
      shouldUseHistoryBack({
        historyLength: 3,
        referrer: "https://github.com/humeo/repocraft-test/issues/33",
        origin: "https://catocode.com",
      })
    ).toBe(false);
  });
});
