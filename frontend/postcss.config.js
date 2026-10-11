import postcssGlobalData from "@csstools/postcss-global-data";
import postcssCustomMedia from "postcss-custom-media";

// Брейкпоинты — токены в одном файле; каждый модуль видит их как @custom-media.
export default {
  plugins: [postcssGlobalData({ files: ["src/shared/styles/media.css"] }), postcssCustomMedia()],
};
