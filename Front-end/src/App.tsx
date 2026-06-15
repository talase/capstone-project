/* ============================================================
   Aegis · App
   ------------------------------------------------------------
   The root component. It sets up client-side routing and the
   overall page layout: a persistent Sidebar on the left and a
   <main> area on the right where the routed page is rendered.
   Each URL maps to one page component. A "*" catch-all redirects
   unknown paths back to the Dashboard.

   The inner <Shell> uses useLocation() so we can re-key the page
   wrapper on every navigation — that restarts its fade-in
   animation, giving a subtle transition between pages.
   ============================================================ */

import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Approvals from "./pages/Approvals";
import Governance from "./pages/Governance";
import History from "./pages/History";
import PersonalContext from "./pages/PersonalContext";
import Contacts from "./pages/Contacts";
import UploadFiles from "./pages/UploadFiles";
import styles from "./App.module.css";

function Shell() {
  const location = useLocation();

  return (
    <div className={styles.layout}>
      <Sidebar />
      <main className={styles.main}>
        <div className={styles.page} key={location.pathname}>
          <Routes location={location}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/governance" element={<Governance />} />
            <Route path="/history" element={<History />} />
            <Route path="/context" element={<PersonalContext />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/upload" element={<UploadFiles />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}

export default App;
