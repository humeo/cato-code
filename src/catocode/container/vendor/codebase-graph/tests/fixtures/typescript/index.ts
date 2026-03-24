import { Config, createConfig, formatUrl } from "./helpers";

interface AppState {
  config: Config;
  running: boolean;
}

function initApp(): AppState {
  const config = createConfig("https://api.example.com");
  return { config, running: true };
}

export class App {
  private state: AppState;

  constructor() {
    this.state = initApp();
  }

  getUrl(path: string): string {
    return formatUrl(this.state.config.apiUrl, path);
  }

  start(): void {
    console.log("Starting app");
  }
}
