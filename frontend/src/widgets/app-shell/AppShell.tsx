// Каркас страницы: неподвижная шапка со знаком, разделами роли и переключателем ролей; меняется только центр.
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";

import { useSession } from "@/entities/session";
import { ResetDemo } from "@/features/reset-demo";
import { RoleSwitcher } from "@/features/role-switch";
import { ru } from "@/shared/i18n/ru";
import { Wordmark } from "@/shared/ui/Wordmark";

import styles from "./AppShell.module.css";

export interface NavItem {
  to: string;
  label: string;
}

interface AppShellProps {
  nav: readonly NavItem[];
  children: ReactNode;
}

export function AppShell({ nav, children }: AppShellProps) {
  const session = useSession();
  return (
    <div className={styles.shell}>
      <a href="#content" className={styles.skip}>
        {ru.shell.skipToContent}
      </a>
      <header className={styles.header}>
        <div className={styles.bar}>
          <Link to="/" className={styles.home}>
            <Wordmark />
          </Link>
          {nav.length > 0 ? (
            <nav className={styles.nav} aria-label={ru.shell.navigation}>
              {nav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end
                  className={({ isActive }) => [styles.link, isActive ? styles.active : ""].join(" ")}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          ) : null}
          <div className={styles.tools}>
            <RoleSwitcher />
            {session.realmId !== null ? <ResetDemo /> : null}
          </div>
        </div>
      </header>
      <main id="content" className={styles.main}>
        {children}
      </main>
    </div>
  );
}
