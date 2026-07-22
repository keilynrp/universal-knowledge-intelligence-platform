import { createRequire } from "node:module";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Declare the React version rather than letting eslint-plugin-react detect it.
// Its auto-detection probes the filesystem through an ESLint-9-era context API
// and throws under ESLint 10 ("contextOrFilename.getFilename is not a
// function") on some platforms (observed on Windows), taking down the entire
// lint run — including files it was never asked to lint.
//
// This is not a relaxation: the value read here is the installed version,
// which is exactly what a working detection would have returned, so
// version-gated rules behave identically. Reading it from the package keeps
// this correct across React upgrades instead of hardcoding a number that
// silently goes stale.
const reactVersion = createRequire(import.meta.url)("react/package.json").version;

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  { settings: { react: { version: reactVersion } } },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
