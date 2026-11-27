import { Link, Route, Routes } from "react-router-dom";
import { Demo } from "./pages/Demo";
import { Workspace } from "./pages/Workspace";
import { SessionProvider } from "./session";

export default function App() {
  return (
    <SessionProvider>
      <div className="app">
        <header className="app-header">
          <Link to="/" className="brand">CV Coach</Link>
          <Link to="/demo" className="header-link">Explore the demo</Link>
        </header>
        <main>
          <Routes>
            <Route path="/demo" element={<Demo />} />
            <Route path="*" element={<Workspace />} />
          </Routes>
        </main>
      </div>
    </SessionProvider>
  );
}
