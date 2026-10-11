// Статус дела точкой и словом: цвет — только у «передано выше» (срок разбора прошёл), остальные серые.
import { Badge } from "@/shared/ui/Badge";

export function CaseStatusBadge({ status, title }: { status: string; title: string }) {
  return (
    <Badge tone={status === "escalated" ? "orange" : "neutral"} dot>
      {title}
    </Badge>
  );
}
