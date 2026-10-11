// Вид графа дела: форма узла различает тип, оттенок серого — тип связи, цвет — только уровень заявки.
// Значения цветов и длительности берутся из токенов (tokens.css), здесь только соответствие «тип → токен».
import type cytoscape from "cytoscape";

export type NodeShape =
  | "round-rectangle"
  | "ellipse"
  | "diamond"
  | "rectangle"
  | "hexagon"
  | "pentagon"
  | "octagon"
  | "triangle"
  | "star"
  | "rhomboid";

export const APPLICATION = "application";

export const NODE_SHAPES: Readonly<Record<string, NodeShape>> = {
  application: "round-rectangle",
  person: "ellipse",
  phone: "diamond",
  device: "rectangle",
  address: "hexagon",
  employer: "pentagon",
  supplier: "octagon",
  helper: "triangle",
  employee: "star",
  card: "rhomboid",
};
export const DEFAULT_SHAPE: NodeShape = "ellipse";

/** Тип связи → токен серого: главные типы (Блок 5) — темнее, служебная связь «заявитель» — светлее. */
export const EDGE_SHADES: Readonly<Record<string, string>> = {
  shared_identifier: "--color-text",
  contract_payment: "--color-gray",
  recommendation: "--color-gray",
  transfer: "--color-gray",
  referral: "--color-gray",
  processed_by: "--color-gray-2",
  applicant: "--color-gray-3",
};
export const DEFAULT_EDGE_SHADE = "--color-gray-2";

export const LEVEL_TOKENS: Readonly<Record<string, string>> = {
  green: "--color-green",
  yellow: "--color-yellow",
  red: "--color-red",
};

const PALETTE_TOKENS = [
  "--color-bg",
  "--color-text",
  "--color-gray",
  "--color-gray-2",
  "--color-gray-3",
  "--color-gray-4",
  "--color-gray-5",
  "--color-gray-6",
  "--color-green",
  "--color-yellow",
  "--color-red",
  "--font-text",
  "--duration-slow",
] as const;

type Token = (typeof PALETTE_TOKENS)[number];
export type Palette = Readonly<Record<Token, string>>;

/** Cytoscape рисует на canvas и не видит CSS-переменных — читаем их значения из корня документа. */
export function readPalette(): Palette {
  const computed = getComputedStyle(document.documentElement);
  return Object.fromEntries(
    PALETTE_TOKENS.map((token) => [token, computed.getPropertyValue(token).trim()]),
  ) as Record<Token, string>;
}

/** Длительность спокойной анимации из токена; при prefers-reduced-motion токен равен 0 — без анимации. */
export function motionDuration(palette: Palette): number {
  const value = Number.parseFloat(palette["--duration-slow"]);
  return Number.isFinite(value) ? value : 0;
}

function shade(palette: Palette, token: string): string {
  return token in palette ? palette[token as Token] : palette["--color-gray-2"];
}

export function edgeColor(palette: Palette, type: string): string {
  return shade(palette, EDGE_SHADES[type] ?? DEFAULT_EDGE_SHADE);
}

export function levelColor(palette: Palette, level: string | null): string {
  const token = level === null ? undefined : LEVEL_TOKENS[level];
  return token === undefined ? palette["--color-bg"] : shade(palette, token);
}

export function graphStylesheet(palette: Palette): cytoscape.StylesheetJson {
  return [
    {
      selector: "node",
      style: {
        shape: DEFAULT_SHAPE,
        width: 22,
        height: 22,
        "background-color": palette["--color-gray-5"],
        "border-width": 1,
        "border-color": palette["--color-gray-2"],
        label: "data(label)",
        "font-family": palette["--font-text"],
        "font-size": 10,
        color: palette["--color-text"],
        "text-valign": "bottom",
        "text-margin-y": 4,
        "text-wrap": "ellipsis",
        "text-max-width": "90px",
      },
    },
    ...Object.entries(NODE_SHAPES).map(([type, shape]) => ({
      selector: `node[type = "${type}"]`,
      style: { shape },
    })),
    {
      selector: `node[type = "${APPLICATION}"]`,
      style: {
        width: 34,
        height: 34,
        "background-color": "data(fill)",
        "border-color": palette["--color-text"],
        "font-size": 11,
        "font-weight": 600,
      },
    },
    {
      selector: "edge",
      style: {
        width: 1,
        "line-color": "data(color)",
        "line-style": "dashed",
        "line-dash-pattern": [4, 3],
        "curve-style": "bezier",
      },
    },
    { selector: "edge[?rare]", style: { width: 3, "line-style": "solid" } },
    { selector: "node.focused", style: { "border-width": 3, "border-color": palette["--color-text"] } },
    { selector: ".faded", style: { opacity: 0.2 } },
    { selector: ".hidden", style: { display: "none" } },
  ];
}
