// Значок формы узла для легенды — та же форма, что Cytoscape рисует на графе.
import type { NodeShape } from "./graphStyle";

const POLYGONS: Partial<Record<NodeShape, string>> = {
  diamond: "6,0.5 11.5,6 6,11.5 0.5,6",
  rectangle: "1,1 11,1 11,11 1,11",
  hexagon: "3,1 9,1 11.5,6 9,11 3,11 0.5,6",
  pentagon: "6,0.5 11.5,4.6 9.4,11.5 2.6,11.5 0.5,4.6",
  octagon: "3.6,0.5 8.4,0.5 11.5,3.6 11.5,8.4 8.4,11.5 3.6,11.5 0.5,8.4 0.5,3.6",
  triangle: "6,0.5 11.5,11.5 0.5,11.5",
  star: "6,0.3 7.4,4.2 11.7,4.2 8.2,6.8 9.5,11 6,8.4 2.5,11 3.8,6.8 0.3,4.2 4.6,4.2",
  rhomboid: "3.5,1 11.5,1 8.5,11 0.5,11",
};

interface ShapeIconProps {
  shape: NodeShape;
  fill: string;
  stroke: string;
}

export function ShapeIcon({ shape, fill, stroke }: ShapeIconProps) {
  const points = POLYGONS[shape];
  const paint = { fill, stroke };
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden focusable="false">
      {points !== undefined ? (
        <polygon points={points} style={paint} />
      ) : shape === "round-rectangle" ? (
        <rect x="0.5" y="0.5" width="11" height="11" rx="3" style={paint} />
      ) : (
        <circle cx="6" cy="6" r="5.5" style={paint} />
      )}
    </svg>
  );
}
