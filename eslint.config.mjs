import js from "@eslint/js";
import ts from "typescript-eslint";
import vueParser from "vue-eslint-parser";
export default ts.config(
  { ignores: ["**/dist/**", "**/node_modules/**", "**/.vite/**"] },
  js.configs.recommended,
  ...ts.configs.recommended,
  {
    files: ["**/*.{ts,mjs,vue}"],
    languageOptions: {
      globals: {
        process: "readonly",
        console: "readonly",
        Buffer: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        URL: "readonly",
        fetch: "readonly",
        uni: "readonly",
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        location: "readonly",
        sessionStorage: "readonly",
        localStorage: "readonly",
        crypto: "readonly",
        indexedDB: "readonly",
        defineProps: "readonly",
        defineEmits: "readonly",
        defineExpose: "readonly",
        FileReader: "readonly",
        WebSocket: "readonly",
        FormData: "readonly",
      },
    },
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    files: ["**/*.vue"],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: ts.parser,
        sourceType: "module",
        extraFileExtensions: [".vue"],
      },
    },
    rules: { "no-undef": "off" },
  },
);
