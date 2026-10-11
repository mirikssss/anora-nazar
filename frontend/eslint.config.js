import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

// Слои: app → pages → widgets → features → entities → shared, импорт только вниз.
const layers = ["app", "pages", "widgets", "features", "entities", "shared"];
const upperLayers = (index) =>
  layers.slice(0, index).map((upper) => ({
    group: [`@/${upper}/*`, `@/${upper}`],
    message: `Слой «${layers[index]}» не импортирует слой выше — «${upper}».`,
  }));
const onlyIcons = { name: "lucide-react", message: "Иконки — только через @/shared/icons." };
const layerRules = layers.map((layer, index) => ({
  files: [`src/${layer}/**/*.{ts,tsx}`],
  rules: {
    "no-restricted-imports": ["error", { paths: [onlyIcons], patterns: upperLayers(index) }],
  },
}));

export default tseslint.config(
  {
    ignores: [
      "dist",
      "src/shared/api/generated",
      "vite.config.ts",
      "eslint.config.js",
      "postcss.config.js",
      "scripts",
    ],
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
    },
  },
  ...layerRules,
  {
    files: ["src/shared/icons/**/*.ts"],
    rules: { "no-restricted-imports": ["error", { patterns: upperLayers(layers.length - 1) }] },
  },
);
