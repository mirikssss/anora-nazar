// Страница не для текущей роли: объясняем и предлагаем войти той ролью, у которой есть право.
import { useLocation } from "react-router";

import { useBankRoles, useStaffRoles } from "@/entities/session";
import { bankOptions, RoleOptionList, staffOptions } from "@/features/role-switch";
import { ru } from "@/shared/i18n/ru";
import { Card } from "@/shared/ui/Card";
import { Skeleton } from "@/shared/ui/Skeleton";

export function AccessPrompt({ permission }: { permission: string }) {
  const location = useLocation();
  const bankRoles = useBankRoles();
  const staffRoles = useStaffRoles();
  const options = [...bankOptions(bankRoles.data ?? []), ...staffOptions(staffRoles.data ?? [])].filter(
    (option) => option.choice.role.permissions.includes(permission),
  );
  return (
    <Card title={ru.errors.forbidden} subtitle={ru.entry.switchToAllowed}>
      {bankRoles.isPending || staffRoles.isPending ? (
        <Skeleton rows={2} label={ru.entry.rolesLoading} />
      ) : (
        <RoleOptionList options={options} stayOn={location.pathname + location.search} />
      )}
    </Card>
  );
}
