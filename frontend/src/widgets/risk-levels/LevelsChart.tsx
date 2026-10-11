// Решения по дням: столбцы с наложением по уровням. Показываем количество, а не доли: объём дня
// различается в разы, и доля маленького дня выглядела бы так же весомо, как доля обычного.
import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { useParentSize } from "@visx/responsive";
import { scaleBand, scaleLinear } from "@visx/scale";
import { useState } from "react";

import type { DayLevels } from "@/entities/risk";
import { titleOf, useStaffTexts } from "@/entities/texts";
import { ru } from "@/shared/i18n/ru";
import { formatDate, formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/Card";

import styles from "./LevelsChart.module.css";

const t = ru.risk.overview;

/** Порядок снизу вверх: от обычного потока к остановленным. */
const SERIES = ["green", "yellow", "red", "stopped"] as const;
type Series = (typeof SERIES)[number];

// Геометрия графика (dataviz): высота области, поля под оси, толщина столбца, зазор между сегментами.
const HEIGHT = 240;
const MARGIN = { top: 8, right: 8, bottom: 28, left: 40 };
const MAX_BAR = 24;
const GAP = 2;
const RADIUS = 4;
const Y_TICKS = 4;
const X_LABELS = 6;
const TOOLTIP_OFFSET = 12;

function total(day: DayLevels): number {
  return SERIES.reduce((sum, key) => sum + day[key], 0);
}

/** «01.09» из даты дня: год на оси лишний, он есть в подсказке. */
function shortDay(day: string): string {
  return formatDate(day).slice(0, 5);
}

/** Прямоугольник со скруглённым верхом: край данных скруглён, основание — прямое. */
function topRounded(x: number, y: number, width: number, height: number): string {
  const r = Math.min(RADIUS, width / 2, height);
  return [
    `M${x},${y + height}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + width - r}`,
    `Q${x + width},${y} ${x + width},${y + r}`,
    `V${y + height}`,
    "Z",
  ].join(" ");
}

function useSeriesTitles(): Record<Series, string> {
  const levels = useStaffTexts().data?.levels;
  return {
    green: titleOf(levels, "green"),
    yellow: titleOf(levels, "yellow"),
    red: titleOf(levels, "red"),
    stopped: t.stopped,
  };
}

function Legend({ titles }: { titles: Record<Series, string> }) {
  return (
    <ul className={styles.legend}>
      {SERIES.map((key) => (
        <li key={key} className={styles.legendItem}>
          <span className={[styles.swatch, styles[key]].join(" ")} aria-hidden />
          {titles[key]}
        </li>
      ))}
    </ul>
  );
}

interface TooltipProps {
  day: DayLevels;
  titles: Record<Series, string>;
  /** Центр столбца и ширина графика: подсказка встаёт с той стороны, где есть место. */
  anchor: number;
  width: number;
}

function Tooltip({ day, titles, anchor, width }: TooltipProps) {
  const side =
    anchor > width / 2 ? { right: width - anchor + TOOLTIP_OFFSET } : { left: anchor + TOOLTIP_OFFSET };
  return (
    <div className={styles.tooltip} style={side} role="presentation">
      <p className={styles.tooltipTitle}>{formatDate(day.day)}</p>
      <dl className={styles.tooltipList}>
        {[...SERIES].reverse().map((key) => (
          <div key={key} className={styles.tooltipRow}>
            <dt>
              <span className={[styles.swatch, styles[key]].join(" ")} aria-hidden />
              {titles[key]}
            </dt>
            <dd className="num">{formatNumber(day[key])}</dd>
          </div>
        ))}
        <div className={[styles.tooltipRow, styles.tooltipTotal].join(" ")}>
          <dt>{t.total}</dt>
          <dd className="num">{formatNumber(total(day))}</dd>
        </div>
      </dl>
    </div>
  );
}

/** Та же сводка таблицей — для экранного диктора вместо графика. */
function HiddenTable({ days, titles }: { days: readonly DayLevels[]; titles: Record<Series, string> }) {
  return (
    <table className="visually-hidden">
      <caption>{t.chartLabel}</caption>
      <thead>
        <tr>
          <th scope="col">{t.day}</th>
          {SERIES.map((key) => (
            <th key={key} scope="col">
              {titles[key]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {days.map((day) => (
          <tr key={day.day}>
            <th scope="row">{formatDate(day.day)}</th>
            {SERIES.map((key) => (
              <td key={key}>{formatNumber(day[key])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Plot({ days, titles }: { days: readonly DayLevels[]; titles: Record<Series, string> }) {
  const { parentRef, width } = useParentSize({ debounceTime: 50 });
  const [hovered, setHovered] = useState<number | null>(null);
  const innerWidth = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerHeight = HEIGHT - MARGIN.top - MARGIN.bottom;

  const x = scaleBand<string>({ domain: days.map((day) => day.day), range: [0, innerWidth], padding: 0.2 });
  const y = scaleLinear<number>({
    domain: [0, Math.max(1, ...days.map(total))],
    range: [innerHeight, 0],
    nice: true,
  });
  const barWidth = Math.min(MAX_BAR, x.bandwidth());
  const labelEvery = Math.max(1, Math.ceil(days.length / X_LABELS));
  const hoveredDay = hovered === null ? undefined : days[hovered];

  return (
    <div
      ref={parentRef}
      className={styles.plot}
      onPointerLeave={() => {
        setHovered(null);
      }}
    >
      {width > 0 ? (
        <svg width={width} height={HEIGHT} aria-hidden>
          <Group left={MARGIN.left} top={MARGIN.top}>
            {y.ticks(Y_TICKS).map((tick) => (
              <line key={tick} className={styles.grid} x1={0} x2={innerWidth} y1={y(tick)} y2={y(tick)} />
            ))}
            {days.map((day, index) => {
              const left = (x(day.day) ?? 0) + (x.bandwidth() - barWidth) / 2;
              const present = SERIES.filter((key) => day[key] > 0);
              let base = 0;
              return (
                <g
                  key={day.day}
                  className={hovered !== null && hovered !== index ? styles.dimmed : undefined}
                >
                  {present.map((key, position) => {
                    const top = y(base + day[key]);
                    const bottom = y(base);
                    base += day[key];
                    // Зазор цвета фона между сегментами отделяет их без обводки.
                    const height = Math.max(0, bottom - top - (position > 0 ? GAP : 0));
                    const isTop = position === present.length - 1;
                    return isTop ? (
                      <path key={key} className={styles[key]} d={topRounded(left, top, barWidth, height)} />
                    ) : (
                      <rect
                        key={key}
                        className={styles[key]}
                        x={left}
                        y={top}
                        width={barWidth}
                        height={height}
                      />
                    );
                  })}
                  <rect
                    className={styles.hit}
                    x={x(day.day) ?? 0}
                    y={0}
                    width={x.step()}
                    height={innerHeight}
                    onPointerEnter={() => {
                      setHovered(index);
                    }}
                  />
                </g>
              );
            })}
            <g className={styles.axis}>
              <AxisLeft
                scale={y}
                numTicks={Y_TICKS}
                hideAxisLine
                hideTicks
                tickFormat={(value) => formatNumber(Number(value))}
              />
              <AxisBottom
                scale={x}
                top={innerHeight}
                hideTicks
                tickValues={days.filter((_, index) => index % labelEvery === 0).map((day) => day.day)}
                tickFormat={shortDay}
              />
            </g>
          </Group>
        </svg>
      ) : null}
      {hoveredDay !== undefined ? (
        <Tooltip
          day={hoveredDay}
          titles={titles}
          anchor={MARGIN.left + (x(hoveredDay.day) ?? 0) + x.bandwidth() / 2}
          width={width}
        />
      ) : null}
    </div>
  );
}

export function LevelsChart({ days }: { days: readonly DayLevels[] }) {
  const titles = useSeriesTitles();
  return (
    <Card title={t.levelsTitle} subtitle={t.levelsSubtitle}>
      <div className={styles.chart}>
        <Legend titles={titles} />
        <Plot days={days} titles={titles} />
        <HiddenTable days={days} titles={titles} />
      </div>
    </Card>
  );
}
