// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 MuVeraAI Corporation

import { defineConfig } from "tsup";

export default defineConfig({
  entry: {
    index: "src/index.ts",
  },
  format: ["esm"],
  target: "es2022",
  dts: true,
  sourcemap: true,
  clean: true,
  splitting: false,
  treeshake: true,
  // Treat peer dependencies as external — do not bundle them
  external: ["vitest", "@aumos/governance"],
  outDir: "dist",
  banner: {
    js: [
      "// SPDX-License-Identifier: Apache-2.0",
      "// Copyright (c) 2026 MuVeraAI Corporation",
    ].join("\n"),
  },
});
