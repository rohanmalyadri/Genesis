export interface AppSettings {
  chunkSize: number[];
  topK: number[];
  cacheTtl: number[];
  model: string;
  inputGuard: boolean;
  contentFilter: boolean;
  outputGuard: boolean;
  showTrace: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  chunkSize: [512],
  topK: [5],
  cacheTtl: [3600],
  model: "gemini-3-flash",
  inputGuard: true,
  contentFilter: true,
  outputGuard: true,
  showTrace: true,
};

const KEY = "genesis_settings";

export function loadSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const saved = window.localStorage.getItem(KEY);
    return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: AppSettings) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(settings));
  } catch {
    /* storage unavailable (private mode): settings just won't persist */
  }
}
