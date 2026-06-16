/* ============================================================
   Aegis - Sidebar
   ------------------------------------------------------------
   The fixed left navigation: brand mark, the list of pages, and
   the light/dark theme toggle at the bottom. NavLink (from React
   Router) automatically adds an "active" class to the link of the
   page you are currently on, which we style as the highlighted item.
   ============================================================ */

import { NavLink } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import {
  CheckShieldIcon,
  DashboardIcon,
  InboxIcon,
  ShieldIcon,
  HistoryIcon,
  UserIcon,
  UsersIcon,
  UploadIcon,
  ClockIcon,
  SunIcon,
  MoonIcon,
} from "./icons";
import styles from "./Sidebar.module.css";

/** The pages shown in the nav. `end` makes "/" match only the exact path. */
const navItems = [
  { to: "/", label: "Dashboard", icon: <DashboardIcon />, end: true },
  { to: "/approvals", label: "Approvals", icon: <InboxIcon />, end: false },
  { to: "/governance", label: "Governance", icon: <ShieldIcon />, end: false },
  { to: "/history", label: "History", icon: <HistoryIcon />, end: false },
  { to: "/context", label: "Personal Context", icon: <UserIcon />, end: false },
  { to: "/contacts", label: "Contacts", icon: <UsersIcon />, end: false },
  { to: "/scheduled-messages", label: "Scheduled Messages", icon: <ClockIcon />, end: false },
  { to: "/upload", label: "Upload Files", icon: <UploadIcon />, end: false },
];

export function Sidebar() {
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className={styles.sidebar}>
      {/* Brand */}
      <div className={styles.brand}>
        <span className={styles.brandMark}>
          <CheckShieldIcon size={20} />
        </span>
        <span className={styles.brandText}>
          <strong>Aegis</strong>
          <small>Assistant Console</small>
        </span>
      </div>

      {/* Navigation */}
      <span className={styles.navLabel}>Menu</span>
      <nav className={styles.nav}>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              isActive ? `${styles.link} ${styles.active}` : styles.link
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Theme toggle */}
      <div className={styles.footer}>
        <button
          className={styles.themeToggle}
          onClick={toggleTheme}
          aria-label="Toggle colour theme"
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
      </div>
    </aside>
  );
}
