import type { JSX } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { DetVerifyDemo } from "./pages/DetVerifyDemo";
import { FullStackDemo } from "./pages/FullStackDemo";
import { Home } from "./pages/Home";
import { HoneynetDemo } from "./pages/HoneynetDemo";
import { RootIDDemo } from "./pages/RootIDDemo";

export default function App(): JSX.Element {
  return (
    <BrowserRouter>
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/rootid" element={<RootIDDemo />} />
          <Route path="/detverify" element={<DetVerifyDemo />} />
          <Route path="/honeynet" element={<HoneynetDemo />} />
          <Route path="/full-stack" element={<FullStackDemo />} />
          <Route
            path="*"
            element={
              <div className="mx-auto max-w-[800px] px-6 py-24">
                <p className="label-eyebrow">404</p>
                <h1 className="mt-4 font-display text-display-lg font-light text-ink">
                  Path not found.
                </h1>
                <p className="mt-3 text-small text-subtext">
                  This route doesn't exist. Try the navigation above.
                </p>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="mt-24 border-t border-rule">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-4 px-6 py-8 md:flex-row md:items-center md:justify-between">
          <p className="font-mono text-label uppercase tracking-wider text-subtext">
            KonnexCore · Spark tier · MIT licence
          </p>
          <p className="font-mono text-label uppercase tracking-wider text-subtext">
            github.com/YoneCode/KonnexCore
          </p>
        </div>
      </footer>
    </BrowserRouter>
  );
}
