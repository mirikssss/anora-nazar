// Бейдж уровня: всегда слово и значок, не только цвет (Блок 5, п. 2).
import { IconAlert, IconError, IconSuccess } from "@/shared/icons";
import { label, ru } from "@/shared/i18n/ru";
import { Badge } from "@/shared/ui/Badge";

import type { Level } from "./model";

const ICONS = { green: IconSuccess, yellow: IconAlert, red: IconError } as const;

interface LevelBadgeProps {
  level: Level | null;
  /** В плотной таблице — точка и слово вместо заливки. */
  compact?: boolean;
}

export function LevelBadge({ level, compact = false }: LevelBadgeProps) {
  if (level === null) {
    return (
      <Badge tone="outline" dot={compact}>
        {ru.application.noLevel}
      </Badge>
    );
  }
  if (compact) {
    return (
      <Badge tone={level} dot>
        {label(ru.levels, level)}
      </Badge>
    );
  }
  const IconComponent = ICONS[level];
  return (
    <Badge tone={level}>
      <IconComponent size={14} aria-hidden />
      {label(ru.levels, level)}
    </Badge>
  );
}
