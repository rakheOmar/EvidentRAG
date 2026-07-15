import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, lazyPlugins } from "vite-plus";

// https://vite.dev/config/
export default defineConfig({
	fmt: {},
	lint: {
		jsPlugins: [{ name: "vite-plus", specifier: "vite-plus/oxlint-plugin" }],
		options: { typeAware: true, typeCheck: true },
		rules: { "vite-plus/prefer-vite-plus-imports": "error" },
	},
	plugins: lazyPlugins(() => [react(), tailwindcss()]),
	resolve: {
		alias: {
			"@": path.resolve(import.meta.dirname, "./src"),
		},
	},
	server: {
		proxy: {
			"/api": "http://localhost:8000",
			"/events": {
				target: "http://localhost:8000",
				ws: true,
			},
		},
	},
});
