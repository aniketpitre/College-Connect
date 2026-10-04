import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { DataTable } from "./DataTable";
import { formatPaise } from "../lib/money";
import { MoneyText } from "./MoneyText";
import { StatusBadge } from "./StatusBadge";

afterEach(cleanup);

describe("formatPaise", () => {
  it("uses Indian digit grouping and two decimals", () => {
    expect(formatPaise(12_500_000)).toBe("₹1,25,000.00");
    expect(formatPaise(4_500_050)).toBe("₹45,000.50");
    expect(formatPaise(0)).toBe("₹0.00");
  });

  it("rejects non-integer paise, so rupee floats never sneak in", () => {
    expect(() => formatPaise(10.5)).toThrow(/integer paise/);
  });

  it("marks negative amounts", () => {
    render(<MoneyText paise={-50_000} />);
    expect(screen.getByText("-₹500.00").className).toContain("negative");
  });
});

interface Row {
  prn: string;
  name: string;
}
const rows: Row[] = Array.from({ length: 30 }, (_, i) => ({ prn: `PRN${String(i).padStart(3, "0")}`, name: i === 7 ? "Aastha Pawar" : `Student ${i}` }));
const columns = [
  { key: "prn", header: "PRN", render: (r: Row) => r.prn, searchText: (r: Row) => r.prn },
  { key: "name", header: "Name", render: (r: Row) => r.name, searchText: (r: Row) => r.name },
];

describe("DataTable", () => {
  it("pages long lists", () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.prn} pageSize={10} />);
    expect(screen.getAllByRole("row")).toHaveLength(11); // header + 10
    expect(screen.getByText("Page 1 of 3 · 30 rows")).toBeTruthy();
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("PRN010")).toBeTruthy();
  });

  it("searches across searchable columns and resets to page 1", () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.prn} pageSize={10} searchPlaceholder="Search students" />);
    fireEvent.click(screen.getByText("Next"));
    fireEvent.change(screen.getByLabelText("Search students"), { target: { value: "aastha" } });
    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("PRN007")).toBeTruthy();
  });

  it("shows an empty state", () => {
    render(<DataTable columns={columns} rows={[]} rowKey={(r) => r.prn} emptyTitle="No students yet" />);
    expect(screen.getByText("No students yet")).toBeTruthy();
  });
});

describe("ConfirmDialog", () => {
  it("requires a reason before confirming when asked to", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open title="Cancel receipt R/2026-27/000123?" message="This needs approval." requireReason onConfirm={onConfirm} onCancel={() => {}} />,
    );
    const confirm = screen.getByText("Confirm") as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Duplicate payment by student" } });
    expect(confirm.disabled).toBe(false);
    act(() => confirm.click());
    expect(onConfirm).toHaveBeenCalledWith("Duplicate payment by student");
  });
});

describe("StatusBadge", () => {
  it("renders its text with a tone class", () => {
    render(<StatusBadge tone="success">Paid</StatusBadge>);
    expect(screen.getByText("Paid").className).toContain("tone-success");
  });
});
