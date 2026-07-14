import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import {
  SidebarStateProvider,
  useSidebarState,
} from "@/components/chat/chat-sidebar";

const SIDEBAR_STORAGE_KEY = "evidentrag:sidebar-collapsed";

function SidebarStateProbe() {
  const { collapsed, setCollapsed } = useSidebarState();
  return (
    <button onClick={() => setCollapsed((current) => !current)} type="button">
      {collapsed ? "collapsed" : "expanded"}
    </button>
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
});

it("restores the collapsed sidebar state from the previous session", () => {
  window.localStorage.setItem(SIDEBAR_STORAGE_KEY, "true");

  render(
    <SidebarStateProvider>
      <SidebarStateProbe />
    </SidebarStateProvider>
  );

  expect(screen.getByText("collapsed")).toBeInTheDocument();
});

it("persists sidebar changes for the next session", () => {
  render(
    <SidebarStateProvider>
      <SidebarStateProbe />
    </SidebarStateProvider>
  );

  fireEvent.click(screen.getByRole("button", { name: "expanded" }));

  expect(window.localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe("true");
});
