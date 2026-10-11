// Выпадающий переключатель ролей, сгруппированный по «Банк (имитатор)» и «Anora Nazar».
import { useBankRoles, useSession, useStaffRoles } from "@/entities/session";
import { ru } from "@/shared/i18n/ru";
import { Dropdown, type DropdownGroup } from "@/shared/ui/Dropdown";

import { bankOptions, isCurrent, staffOptions, type RoleOption } from "./roleOptions";
import { useChooseRole } from "./useChooseRole";

export function RoleSwitcher() {
  const session = useSession();
  const staffRoles = useStaffRoles();
  const bankRoles = useBankRoles();
  const choose = useChooseRole();

  const toItems = (options: RoleOption[]) =>
    options.map((option) => ({
      key: option.key,
      label: option.label,
      description: option.description,
      selected: isCurrent(option, session.identity),
      onSelect: () => {
        choose.mutate(option.choice);
      },
    }));

  const groups: DropdownGroup[] = [
    { key: "bank", title: ru.roleGroups.bank, items: toItems(bankOptions(bankRoles.data ?? [])) },
    { key: "product", title: ru.roleGroups.product, items: toItems(staffOptions(staffRoles.data ?? [])) },
  ];

  const identity = session.identity;
  const current =
    identity === null
      ? ru.shell.chooseRole
      : identity.kind === "bank"
        ? identity.title
        : identity.displayName;

  return <Dropdown trigger={current} label={ru.shell.roleSwitcher} groups={groups} />;
}
