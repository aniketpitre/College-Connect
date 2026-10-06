import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const student = makeMe({ kind: "student", name: "Rohan Patil", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
const office = makeMe({ roles: ["office"], permissions: ["notices.read", "notices.publish", "kb.manage", "analytics.view", "setup.read"] });
const notice = {
  id: "n1",
  title: "Exam form",
  body: "Submit by 15 October.",
  hi: null,
  mr: null,
  audience: { kind: "students" },
  audience_label: "All students",
  publish_at: "2026-10-01T05:00:00Z",
  expires_on: null,
  pinned: false,
  public: false,
  state: "published",
  has_attachment: false,
  author: null,
  emailed: 0,
};

describe("deadline radar", () => {
  it("a student sees a confirmed deadline on the home page in Marathi", async () => {
    localStorage.setItem("cc-lang", "mr");
    const home = {
      name: "Rohan Patil",
      prn: "2026BCA001",
      class: "BCA · FY",
      academic_year: "2026-27",
      photo_url: null,
      balance: 0,
      attendance: null,
      cards: [
        {
          kind: "deadline",
          severity: "warning",
          title: "Submit the exam form",
          what_mr: "परीक्षा अर्ज जमा करा",
          due_date: "2026-10-15",
          days_left: 1,
          notice_id: "n1",
        },
      ],
    };
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/home") return { status: 200, body: home };
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByText(/परीक्षा अर्ज जमा करा: .* पर्यंत \(उद्या\)/)).toBeTruthy();
  });

  it("office confirms a found date and adds one", async () => {
    let list = [{ id: "d1", notice_id: "n1", date: "2026-10-15", what: { en: "Submit by 15 October" }, status: "proposed", source: "pattern" }];
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/notices/n1") return { status: 200, body: notice };
      if (path === "/notices/n1/deadlines" && method === "GET") return { status: 200, body: list };
      if (path === "/deadlines/d1") {
        list = [{ ...list[0], status: "confirmed" }];
        return { status: 200, body: list[0] };
      }
      if (path === "/notices/n1/deadlines" && method === "POST") return { status: 201, body: {} };
      return { status: 404 };
    });
    renderApp("/app/notices/n1");
    expect(await screen.findByText("found in the text")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(screen.getByText("confirmed")).toBeTruthy());
    expect(calls.find((c) => c.path === "/deadlines/d1")?.body).toEqual({ status: "confirmed" });
    fireEvent.change(screen.getByLabelText("Deadline date"), { target: { value: "2026-10-30" } });
    fireEvent.change(screen.getByLabelText("What students must do"), { target: { value: "Collect hall tickets" } });
    fireEvent.click(screen.getByRole("button", { name: "Add a deadline" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST" && c.path === "/notices/n1/deadlines")?.body).toEqual({ date: "2026-10-30", what: "Collect hall tickets" }),
    );
  });
});

describe("knowledge gaps", () => {
  it("the dashboard counts unanswered questions and the office answers one as an FAQ", async () => {
    let gaps = [{ key: "is there a canteen menu", question: "Is there a canteen menu?", count: 3, languages: ["en", "mr"], last_at: "2026-10-06T05:00:00Z" }];
    const kb = {
      documents: [],
      categories: ["notices", "hostel"],
      status: { retrieval: "bm25", generation: "extractive", chunks: 0, documents: 0, embeddings_configured: false, chunks_total: 0, chunks_embedded: 0 },
    };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/dashboard") return { status: 200, body: { help_desk: { unanswered: 1, asked: 3, top: gaps } } };
      if (path === "/kb/documents") return { status: 200, body: kb };
      if (path === "/kb/gaps") return { status: 200, body: gaps };
      if (path === "/kb/gaps/answer") {
        gaps = [];
        return { status: 201, body: { id: "k1", title: "FAQ: Is there a canteen menu?", questions_closed: 3 } };
      }
      return { status: 404 };
    });
    renderApp("/app");
    expect(await screen.findByText("Questions it couldn't answer (7 days)")).toBeTruthy();
    expect(screen.getByText("Is there a canteen menu?")).toBeTruthy();
    fireEvent.click(screen.getByText("Questions it couldn't answer (7 days)"));

    expect(await screen.findByRole("heading", { name: "Questions the help desk couldn't answer" })).toBeTruthy();
    expect(await screen.findByText(/asked 3 times · English, Marathi/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Make a notice" }).getAttribute("href")).toBe("/app/notices?draft=Is%20there%20a%20canteen%20menu%3F");
    fireEvent.click(screen.getByRole("button", { name: "Answer as FAQ" }));
    const item = screen.getByText("Is there a canteen menu?", { selector: "b" }).closest("li")!;
    fireEvent.change(within(item).getByLabelText("Answer"), { target: { value: "The menu is on the board near the library." } });
    fireEvent.change(within(item).getByLabelText("Office"), { target: { value: "hostel" } });
    fireEvent.click(within(item).getByRole("button", { name: "Save the FAQ" }));
    expect(await screen.findByText(/3 questions answered/)).toBeTruthy();
    expect(calls.find((c) => c.path === "/kb/gaps/answer")?.body).toMatchObject({ key: "is there a canteen menu", category: "hostel", audience: "public" });
  });
});
