interface AppConfig {
    apiBaseUrl: string;
}

class ConfigService {
    private static config: AppConfig;

    static async load(): Promise<void> {
        const response = await fetch("./config.json");

        if (!response.ok) {
            throw new Error("Failed to load config.json");
        }

        const config: AppConfig = await response.json();

        if (!config.apiBaseUrl?.trim()) {
            throw new Error("apiBaseUrl is missing");
        }

        this.config = {
            apiBaseUrl: config.apiBaseUrl.replace(/\/+$/, "")
        };
    }

    static get apiBaseUrl(): string {
        if (!this.config) {
            throw new Error("Configuration not initialized");
        }

        return this.config.apiBaseUrl;
    }
}