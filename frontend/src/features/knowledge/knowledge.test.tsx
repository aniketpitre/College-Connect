import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const office = makeMe({ roles: ["office"], permissions: ["kb.manage", "notices.publish", "analytics.view"] });
const doc = (id: string, title: string, source: string, audience = "public", notice_id: string | null = null) => ({
  id,
  title,
  document: `${title}.pdf`,
  category: "fees",
  audience,
  source,
  notice_id,
  chunks: 3,
  created_at: "2026-10-06T05:00:00Z",
  created_by: null,
});

describe("help desk documents", () => {
  it("office adds a typed document, sees notices separately and removes a document", async () => {
    let docs = [doc("d1", "Fee Structure 2026", "bundled"), doc("d2", "Holiday on Monday", "notice", "everyone", "n1")];
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/kb/documents" && method === "GET")
        return {
          status: 200,
          body: {
            documents: docs,
            categories: ["admissions", "fees", "notices"],
            status: { retrieval: "bm25", generation: "extractive", chunks: 9, documents: 2, embeddings_configured: false, chunks_total: 9, chunks_embedded: 0 },
          },
        };
      if (path === "/kb/documents" && method === "POST") {
        docs = [...docs, doc("d3", "Gymkhana timings", "text", "everyone")];
        return { status: 201, body: docs[2] };
      }
      if (path === "/kb/documents/d1" && method === "DELETE") {
        docs = docs.filter((d) => d.id !== "d1");
        return { status: 200, body: { ok: true } };
      }
      return { status: 404 };
    });
    renderApp("/app/knowledge");
    expect(await screen.findByText("Fee Structure 2026")).toBeTruthy();
    expect(screen.getByText(/search by keywords/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Holiday on Monday" }).getAttribute("href")).toBe("/app/notices/n1");

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Gymkhana timings" } });
    fireEvent.change(screen.getByLabelText("Who gets answers from it"), { target: { value: "everyone" } });
    fireEvent.change(screen.getByLabelText(/or type the text/), { target: { value: "## Hours\nOpen 6 am to 9 pm." } });
    fireEvent.click(screen.getByRole("button", { name: "Add to the help desk" }));
    expect(await screen.findByText("Gymkhana timings")).toBeTruthy();
    const form = calls.find((c) => c.method === "POST")?.body as FormData;
    expect(form.get("audience")).toBe("everyone");
    expect(form.get("text")).toContain("Open 6 am");

    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(2); // notices are withdrawn on the notice itself
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(screen.queryByText("Fee Structure 2026")).toBeNull());
  });
});
