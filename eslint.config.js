// ESLint for the website (web/src) and its tests (tests/web); Prettier owns formatting.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["node_modules/", "web/dist/", ".tools/", ".cache/", ".venv/"] },
  {
    files: ["web/**/*.{ts,tsx}", "tests/web/**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.flat["recommended-latest"].rules,
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    files: ["tests/web/**/*.{ts,tsx}", "web/src/test/**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.vitest } },
  },
  {
    // Nico's pasted component stays as pasted: it writes a ref during render and keys its
    // effect on a joined string, which the React Compiler rules flag.
    files: ["web/src/components/ui/halftone-wordmark-footer.tsx"],
    rules: {
      "react-hooks/refs": "off",
      "react-hooks/exhaustive-deps": "off",
      "react-hooks/immutability": "off",
      "react-hooks/purity": "off",
    },
  },
);
