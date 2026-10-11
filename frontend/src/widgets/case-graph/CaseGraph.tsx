// Подграф дела (Oracle ECM network analysis): кто с кем и через что связан. Фильтр типов связей служит
// и легендой связей; выбор заявки подсвечивает её и соседей, остальное приглушается.
import cytoscape from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";

import type { CaseGraph as CaseGraphData } from "@/entities/case";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { IconReset } from "@/shared/icons";
import { label, ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";

import styles from "./CaseGraph.module.css";
import {
  APPLICATION,
  DEFAULT_EDGE_SHADE,
  DEFAULT_SHAPE,
  EDGE_SHADES,
  LEVEL_TOKENS,
  NODE_SHAPES,
  edgeColor,
  graphStylesheet,
  levelColor,
  motionDuration,
  readPalette,
  type Palette,
} from "./graphStyle";
import { ShapeIcon } from "./ShapeIcon";

const t = ru.control.graph;
const PADDING = 24;

interface CaseGraphProps {
  graph: CaseGraphData;
  selectedApplicationId: string | null;
  onSelectApplication: (applicationId: string) => void;
}

/** Узел, выбранный на графе, действует, пока не сменилась выбранная заявка. */
interface NodeFocus {
  nodeId: string;
  forApplication: string | null;
}

function dataString(element: cytoscape.SingularElementArgument, key: string): string | null {
  const value: unknown = element.data(key);
  return typeof value === "string" ? value : null;
}

function toElements(graph: CaseGraphData, palette: Palette): cytoscape.ElementDefinition[] {
  const ids = new Set(graph.nodes.map((node) => node.id));
  return [
    ...graph.nodes.map((node) => ({
      group: "nodes" as const,
      data: {
        id: node.id,
        type: node.type,
        label: node.display,
        applicationId: node.application_id,
        fill: levelColor(palette, node.level),
      },
    })),
    ...graph.edges
      .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
      .map((edge, index) => ({
        group: "edges" as const,
        data: {
          id: `edge-${String(index)}`,
          source: edge.source,
          target: edge.target,
          type: edge.type,
          rare: edge.rare,
          color: edgeColor(palette, edge.type),
        },
      })),
  ];
}

function distinct(values: readonly string[]): string[] {
  return [...new Set(values)];
}

export function CaseGraph({ graph, selectedApplicationId, onSelectApplication }: CaseGraphProps) {
  const levels = useStaffTexts().data?.levels;
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const durationRef = useRef(0);
  const onSelectRef = useRef(onSelectApplication);
  const selectedRef = useRef(selectedApplicationId);
  const [hiddenTypes, setHiddenTypes] = useState<ReadonlySet<string>>(new Set());
  const [nodeFocus, setNodeFocus] = useState<NodeFocus | null>(null);

  const edgeTypes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const edge of graph.edges) counts.set(edge.type, (counts.get(edge.type) ?? 0) + 1);
    return [...counts.entries()];
  }, [graph]);
  const nodeTypes = useMemo(() => distinct(graph.nodes.map((node) => node.type)), [graph]);
  const nodeLevels = useMemo(
    () =>
      distinct(
        graph.nodes.flatMap((node) => (node.type === APPLICATION && node.level !== null ? [node.level] : [])),
      ),
    [graph],
  );

  const selectedNodeId = graph.nodes.find((node) => node.application_id === selectedApplicationId)?.id;
  const focusedNodeId =
    nodeFocus !== null && nodeFocus.forApplication === selectedApplicationId
      ? nodeFocus.nodeId
      : (selectedNodeId ?? null);
  const focusedNode = graph.nodes.find((node) => node.id === focusedNodeId) ?? null;
  const linkedApplications =
    focusedNode !== null && focusedNode.type !== APPLICATION
      ? graph.edges.flatMap((edge) => {
          const other =
            edge.source === focusedNode.id
              ? edge.target
              : edge.target === focusedNode.id
                ? edge.source
                : null;
          const node = graph.nodes.find((item) => item.id === other && item.type === APPLICATION);
          return node === undefined ? [] : [node.display];
        })
      : [];

  useEffect(() => {
    onSelectRef.current = onSelectApplication;
    selectedRef.current = selectedApplicationId;
  });

  useEffect(() => {
    const container = containerRef.current;
    if (container === null) return;
    const palette = readPalette();
    durationRef.current = motionDuration(palette);
    const cy = cytoscape({
      container,
      elements: toElements(graph, palette),
      style: graphStylesheet(palette),
      minZoom: 0.3,
      maxZoom: 3,
      boxSelectionEnabled: false,
      autounselectify: true,
      // Колесо прокручивает страницу, а не масштаб графа: иначе страница дела «застревает» на графе.
      userZoomingEnabled: false,
    });
    cy.layout({
      name: "cose",
      // Раскладка без анимации: узлы не «прыгают» при открытии дела.
      animate: false,
      fit: true,
      padding: PADDING,
      nodeDimensionsIncludeLabels: true,
    }).run();
    cy.on("tap", "node", (event) => {
      const node = event.target as cytoscape.NodeSingular;
      const applicationId = dataString(node, "applicationId");
      if (applicationId !== null) {
        setNodeFocus(null);
        onSelectRef.current(applicationId);
      } else {
        setNodeFocus({ nodeId: node.id(), forApplication: selectedRef.current });
      }
    });
    cy.on("tap", (event) => {
      if (event.target === cy) setNodeFocus(null);
    });
    const observer = new ResizeObserver(() => {
      cy.resize();
    });
    observer.observe(container);
    cyRef.current = cy;
    return () => {
      observer.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph]);

  useEffect(() => {
    const cy = cyRef.current;
    if (cy === null) return;
    cy.batch(() => {
      cy.edges().forEach((edge) => {
        edge.toggleClass("hidden", hiddenTypes.has(dataString(edge, "type") ?? ""));
      });
      // Идентификатор без видимых связей ничего не объясняет — прячем вместе с его связями.
      cy.nodes().forEach((node) => {
        const orphan = node.connectedEdges().not(".hidden").empty();
        node.toggleClass("hidden", dataString(node, "type") !== APPLICATION && orphan);
      });
    });
  }, [graph, hiddenTypes]);

  useEffect(() => {
    const cy = cyRef.current;
    if (cy === null) return;
    cy.batch(() => {
      cy.elements().removeClass("faded focused");
      if (focusedNodeId === null) return;
      const node = cy.getElementById(focusedNodeId);
      if (node.empty()) return;
      node.addClass("focused");
      cy.elements().not(node.closedNeighborhood()).addClass("faded");
    });
  }, [graph, focusedNodeId]);

  const toggleType = (type: string) => {
    setHiddenTypes((current) => {
      const next = new Set(current);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const fit = () => {
    const cy = cyRef.current;
    if (cy === null) return;
    cy.animate(
      { fit: { eles: cy.elements(":visible"), padding: PADDING } },
      { duration: durationRef.current },
    );
  };

  return (
    <div className={styles.graph}>
      <div className={styles.toolbar}>
        <div className={styles.filters} role="group" aria-label={t.filter}>
          {edgeTypes.map(([type, count]) => (
            <button
              key={type}
              type="button"
              className={styles.chip}
              aria-pressed={!hiddenTypes.has(type)}
              onClick={() => {
                toggleType(type);
              }}
            >
              <span
                className={styles.line}
                style={{ borderTopColor: `var(${EDGE_SHADES[type] ?? DEFAULT_EDGE_SHADE})` }}
                aria-hidden
              />
              <span>{label(t.edgeTypes, type)}</span>
              <span className={styles.count}>{count}</span>
            </button>
          ))}
        </div>
        <Button size="sm" variant="ghost" icon={IconReset} onClick={fit}>
          {t.fit}
        </Button>
      </div>

      <div ref={containerRef} className={styles.canvas} role="img" aria-label={t.label} />

      {focusedNode !== null && focusedNode.type !== APPLICATION ? (
        <p className={styles.caption}>
          <span className={styles.captionType}>{label(t.nodeTypes, focusedNode.type)}</span>{" "}
          <span className="num">{focusedNode.display}</span>
          {linkedApplications.length > 0
            ? ` · ${t.linkedApplications}: ${distinct(linkedApplications).join(", ")}`
            : null}
        </p>
      ) : null}

      <div className={styles.legend} aria-label={t.legend}>
        <div className={styles.legendGroup}>
          <span className={styles.legendTitle}>{t.nodesLegend}</span>
          {nodeTypes.map((type) => (
            <span key={type} className={styles.legendItem}>
              <ShapeIcon
                shape={NODE_SHAPES[type] ?? DEFAULT_SHAPE}
                fill={type === APPLICATION ? "var(--color-bg)" : "var(--color-gray-5)"}
                stroke={type === APPLICATION ? "var(--color-text)" : "var(--color-gray-2)"}
              />
              {label(t.nodeTypes, type)}
            </span>
          ))}
        </div>
        {nodeLevels.length > 0 ? (
          <div className={styles.legendGroup}>
            <span className={styles.legendTitle}>{t.levelsLegend}</span>
            {nodeLevels.map((level) => (
              <span key={level} className={styles.legendItem}>
                <span
                  className={styles.dot}
                  style={{ background: `var(${LEVEL_TOKENS[level] ?? "--color-bg"})` }}
                  aria-hidden
                />
                {titleOf(levels, level)}
              </span>
            ))}
          </div>
        ) : null}
        <div className={styles.legendGroup}>
          <span className={styles.legendTitle}>{t.linksLegend}</span>
          <span className={styles.legendItem}>
            <span className={styles.rare} aria-hidden />
            {t.rare}
          </span>
          <span className={styles.legendItem}>
            <span className={styles.frequent} aria-hidden />
            {t.frequent}
          </span>
        </div>
      </div>
    </div>
  );
}
