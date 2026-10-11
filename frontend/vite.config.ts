import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Адреса сервисов — из окружения compose; фронт ходит в них через один адрес и прокси.
function required(env: Record<string, string>, name: string): string {
  const value = env[name];
  if (!value) throw new Error(`Не задана переменная окружения ${name}`);
  return value;
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxy =
    command === "serve"
      ? {
          [required(env, "VITE_NODE_API_BASE")]: {
            target: required(env, "WEB_NODE_UPSTREAM"),
            rewrite: (path: string) => path.replace(env.VITE_NODE_API_BASE ?? "", ""),
          },
          [required(env, "VITE_BANK_API_BASE")]: {
            target: required(env, "WEB_BANK_UPSTREAM"),
            rewrite: (path: string) => path.replace(env.VITE_BANK_API_BASE ?? "", ""),
          },
        }
      : undefined;
  return {
    plugins: [react()],
    resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
    server: { port: Number(required(env, "WEB_PORT")), strictPort: true, proxy },
  };
});
