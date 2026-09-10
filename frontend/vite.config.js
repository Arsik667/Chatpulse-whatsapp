import react from "@vitejs/plugin-react";
import { defineConfig, searchForWorkspaceRoot } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // strictPort: бэкенд пускает по CORS только :5173, так что молча переезжать
    // на другой порт нельзя — лучше упасть с понятной ошибкой.
    port: 5173,
    strictPort: true,
    // демо-чат лежит в ../examples (его же используют тесты бэкенда)
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), "../examples"] },
  },
  preview: { port: 5173, strictPort: true },
});
