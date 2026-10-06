import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const notice = {
  id: "n1", title: "Exam form deadline", body: "Submit by Friday.", hi: null, mr: { title: "परीक्षा अर्जाची मुदत", body: "शुक्रवारपर्यंत अर्ज भरा." },
  audience: { kind: "students" }, audience_label: "All students", publish_at: "2026-10-01T05:00:00Z", expires_on: null, pinned: true,
  state: "published", has_attachment: true, author: "Sunil Gaikwad", emailed: 0,
};
const student = makeMe({ kind: "student", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
const office = makeMe({ roles: ["office"], permissions: ["notices.read", "notices.publish", "setup.read"] });

describe("notices", () => {
  it("a student reads a notice in Marathi with its PDF", async () => {
    localStorage.setItem("cc-lang", "mr");
    mockApi((_m, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path.startsWith("/notices?")) return { status: 200, body: [notice] };
      if (path === "/notices/n1") return { status: 200, body: notice };
      return { status: 404 };
    });
    renderApp("/app/notices");
    expect(await screen.findByText("परीक्षा अर्जाची मुदत")).toBeTruthy();
    expect(screen.getByText("महत्त्वाची")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "New notice" })).toBeNull();
    fireEvent.click(screen.getByText("परीक्षा अर्जाची मुदत"));
    expect(await screen.findByText("शुक्रवारपर्यंत अर्ज भरा.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "PDF उघडा" }).getAttribute("href")).toBe("/api/v1/notices/n1/attachment");
    expect(screen.queryByText("Manage (staff)")).toBeNull();
  });

  it("office publishes a notice to a class and emails it", async () => {
    const setup = {
      institution: {}, current_year: null, academic_years: [], departments: [], categories: [],
      programmes: [{ id: "p1", status: "active", code: "BCA", name: "BCA", department_id: "d1", level: "UG", duration_years: 3, semesters_per_year: 2, year_labels: ["FY", "SY", "TY"] }],
      divisions: [{ id: "v1", status: "active", programme_id: "p1", year_of_study: 1, name: "A", capacity: 60 }],
    };
    let emailed = 0;
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/setup") return { status: 200, body: setup };
      if (path.startsWith("/notices?")) return { status: 200, body: [] };
      if (path === "/notices" && method === "POST") return { status: 201, body: { ...notice, id: "n2" } };
      if (path === "/notices/n2") return { status: 200, body: { ...notice, id: "n2", emailed } };
      if (path === "/notices/n2/email") {
        emailed += 100;
        return { status: 200, body: { sent: 100, failed: 0, emailed, audience: 150, remaining: 150 - emailed, done: emailed >= 150 } };
      }
      return { status: 404 };
    });
    renderApp("/app/notices");
    fireEvent.click(await screen.findByRole("button", { name: "New notice" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Practical exam timetable" } });
    fireEvent.change(within(dialog).getByLabelText("Audience"), { target: { value: "class" } });
    await within(dialog).findByRole("option", { name: /BCA/ });
    fireEvent.change(within(dialog).getByLabelText("Programme"), { target: { value: "p1" } });
    fireEvent.change(within(dialog).getByLabelText("Year"), { target: { value: "1" } });
    fireEvent.change(within(dialog).getByLabelText("Division"), { target: { value: "v1" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Publish" }));
    expect(await screen.findByText("Manage (staff)")).toBeTruthy();
    expect(calls.find((c) => c.method === "POST" && c.path === "/notices")?.body).toMatchObject({
      title: "Practical exam timetable",
      audience: { kind: "class", programme_id: "p1", year_of_study: 1, division_id: "v1" },
      pinned: false,
    });
    fireEvent.click(screen.getByRole("button", { name: "Email the audience" }));
    expect(await screen.findByText(/Emailed 200 of 150|Emailed 150 of 150|Emailed 200/)).toBeTruthy();
    await waitFor(() => expect(calls.filter((c) => c.path === "/notices/n2/email")).toHaveLength(2));
  });

  it("office translates a notice to Hindi and Marathi before publishing", async () => {
    const setup = { institution: {}, current_year: null, academic_years: [], departments: [], categories: [], programmes: [], divisions: [] };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path === "/setup") return { status: 200, body: setup };
      if (path.startsWith("/notices?")) return { status: 200, body: [] };
      if (path === "/notices/translate")
        return { status: 200, body: { hi: { title: "छुट्टी", body: "सोमवार को बंद" }, mr: { title: "सुट्टी", body: "सोमवारी बंद" } } };
      if (path === "/notices" && method === "POST") return { status: 201, body: { ...notice, id: "n3", public: true } };
      if (path === "/notices/n3") return { status: 200, body: { ...notice, id: "n3", public: true } };
      return { status: 404 };
    });
    renderApp("/app/notices");
    fireEvent.click(await screen.findByRole("button", { name: "New notice" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Holiday on Monday" } });
    fireEvent.change(within(dialog).getByLabelText("Text"), { target: { value: "Closed on Monday." } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Hindi \/ Marathi versions/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Translate from English" }));
    await waitFor(() => expect((within(dialog).getByLabelText("Title in Marathi") as HTMLInputElement).value).toBe("सुट्टी"));
    fireEvent.change(within(dialog).getByLabelText("Audience"), { target: { value: "everyone" } });
    fireEvent.click(within(dialog).getByLabelText(/public help desk/));
    fireEvent.click(within(dialog).getByRole("button", { name: "Publish" }));
    expect(await screen.findByText(/also on the public help desk/)).toBeTruthy();
    expect(calls.find((c) => c.method === "POST" && c.path === "/notices")?.body).toMatchObject({
      hi: { title: "छुट्टी", body: "सोमवार को बंद" },
      mr: { title: "सुट्टी", body: "सोमवारी बंद" },
      public: true,
    });
  });
});
