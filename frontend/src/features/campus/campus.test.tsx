import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const student = makeMe({ kind: "student", name: "Rohan Patil", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
const loan = { id: "l1", book_id: "b1", title: "Clean Code", authors: ["Robert C. Martin"], barcode: "LIB000001", issued_on: "2026-09-20", due_date: "2026-10-04", returned_on: null, status: "open", days_late: 1, fine_so_far: 200, fine: 0, renewals: 0 };

describe("campus", () => {
  it("a student sees their library books in Marathi and reserves a book that is out", async () => {
    localStorage.setItem("cc-lang", "mr");
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/library") return { status: 200, body: { rules: { loan_days: 14, max_books: 3, fine_per_day: 200, max_renewals: 1 }, loans: [loan], history: [], reservations: [] } };
      if (path.startsWith("/library/books")) return { status: 200, body: [{ id: "b2", isbn: null, title: "Let Us C", authors: ["Kanetkar"], publisher: "", year: null, subject: "", copies: 2, available: 0, waiting: 0 }] };
      if (path === "/me/library/reservations") return { status: 200, body: {} };
      return { status: method === "GET" ? 404 : 200 };
    });
    renderApp("/app/library");
    expect(await screen.findByText(/1 दिवस उशीर/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "नूतनीकरण" })).toBeNull(); // overdue: no renewal
    fireEvent.click(await screen.findByRole("button", { name: "राखीव करा" }));
    await waitFor(() => expect(calls.find((c) => c.path === "/me/library/reservations")?.body).toEqual({ book_id: "b2" }));
  });

  it("the librarian issues and returns by barcode", async () => {
    const lib = makeMe({ roles: ["librarian"], role_labels: ["Librarian"], permissions: ["library.manage", "library.read"] });
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: lib };
      if (path === "/library/overview") return { status: 200, body: { titles: 1, copies: 2, issued: 1, overdue: 0, reservations: 0, settings: { loan_days: 14, max_books: 3, fine_per_day: 200, max_renewals: 1, hold_days: 2 } } };
      if (path === "/library/issue") return { status: 200, body: { ...loan, days_late: 0, student: { id: "s1", name: "Rohan Patil", prn: "2026BCA001" } } };
      if (path === "/library/return") return { status: 200, body: { ...loan, status: "returned", fine: 1200, student: { id: "s2", name: "Neha Joshi", prn: "2026BCA002" }, held_for_reservation: true } };
      return { status: method === "GET" ? 200 : 404, body: [] };
    });
    renderApp("/app/library");
    fireEvent.change(await screen.findByLabelText("Student PRN"), { target: { value: "2026BCA001" } });
    fireEvent.change(screen.getAllByLabelText("Book barcode (scan)")[0], { target: { value: "LIB000001" } });
    fireEvent.click(screen.getByRole("button", { name: "Issue book" }));
    expect(await screen.findByText(/Issued “Clean Code” to Rohan Patil, due 2026-10-04/)).toBeTruthy();
    fireEvent.change(screen.getAllByLabelText("Book barcode (scan)")[1], { target: { value: "LIB000002" } });
    fireEvent.click(screen.getByRole("button", { name: "Return book" }));
    expect(await screen.findByText(/fine ₹12.00 added to fees.*reserved/)).toBeTruthy();
    expect(calls.find((c) => c.path === "/library/return")?.body).toEqual({ barcode: "LIB000002" });
  });

  it("a hostel resident asks for an out-pass", async () => {
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/hostel")
        return { status: 200, body: { resident: true, allotment: { block: "Shivneri", room: "101", bed: 1, since: "2026-07-01", annual_fee: "₹30,000.00" }, outpasses: [], complaints: [], mess_menu: { mon: "Poha" } } };
      return { status: method === "GET" ? 404 : 201, body: {} };
    });
    renderApp("/app/hostel");
    expect(await screen.findByText("Shivneri, room 101, bed 1")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Leaving"), { target: { value: "2026-10-10T09:00" } });
    fireEvent.change(screen.getByLabelText("Back by"), { target: { value: "2026-10-11T18:00" } });
    fireEvent.change(screen.getByLabelText("Going to"), { target: { value: "Satara" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Family function" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask for an out-pass" }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === "/me/hostel/outpasses")?.body).toEqual({ leave_at: "2026-10-10T09:00:00+05:30", return_by: "2026-10-11T18:00:00+05:30", destination: "Satara", reason: "Family function" }),
    );
    expect(screen.getByText("Poha")).toBeTruthy();
  });

  it("a student sees drives they can join and registers", async () => {
    const drive = {
      id: "d1", company: "Infosys", role: "Systems Engineer", ctc_lpa: 3.6, location: "Pune", description: "", register_by: "2026-10-20", drive_date: null,
      rounds: ["Aptitude", "Interview"], status: "open", open_now: true, eligibility: { programme_ids: [], programmes: [], years: [], min_cgpa: 6, max_backlogs: 0 },
    };
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/me/placement")
        return { status: 200, body: { profile: { skills: "", linkedin: "", resume_name: "cv.pdf", resume_url: "/files/f1" }, cgpa: 8.5, backlogs: 0, drives: [{ ...drive, eligible: true, reasons: [], registration: null }, { ...drive, id: "d2", company: "TCS", eligible: false, reasons: ["cgpa"], registration: null }] } };
      return { status: method === "GET" ? 404 : 200, body: {} };
    });
    renderApp("/app/placement");
    expect(await screen.findByText("Your CGPA 8.5 · backlogs 0")).toBeTruthy();
    expect(screen.getByText(/Not eligible: CGPA/)).toBeTruthy();
    const buttons = screen.getAllByRole("button", { name: "Register" });
    expect(buttons).toHaveLength(1); // only the drive they are eligible for
    fireEvent.click(buttons[0]);
    await waitFor(() => expect(calls.some((c) => c.path === "/me/placement/drives/d1/register")).toBe(true));
  });
});
