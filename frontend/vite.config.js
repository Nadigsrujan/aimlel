import { defineConfig } from "vite";
export default defineConfig({
  server: { proxy: { "/api": "http://127.0.0.1:8080" } },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "three-engine": ["three", "@react-three/fiber", "@react-three/drei"],
          "graph-engine": ["@xyflow/react"],
        },
      },
    },
  },
});
