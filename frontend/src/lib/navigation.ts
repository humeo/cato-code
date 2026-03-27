interface HistoryBackOptions {
  historyLength: number;
  referrer: string;
  origin: string;
}

export function shouldUseHistoryBack({ historyLength, referrer, origin }: HistoryBackOptions): boolean {
  if (historyLength <= 1) return false;
  if (!referrer) return false;

  try {
    const referrerUrl = new URL(referrer);
    return referrerUrl.origin === origin && referrerUrl.pathname.startsWith("/dashboard");
  } catch {
    return false;
  }
}
