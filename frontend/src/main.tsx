// Точка входа приложения.
import "@/shared/styles/base.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/app/App";

const root = document.getElementById("root");
if (root === null) throw new Error("Нет элемента #root в index.html");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
