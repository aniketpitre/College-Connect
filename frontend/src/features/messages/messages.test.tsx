import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("messages", () => {
  it("a parent chooses channels in their language; channels the college hasn't set up are off", async () => {
    localStorage.setItem("cc-lang", "hi");
    const parent = makeMe({ kind: "parent", name: "Suresh Patil", roles: ["parent"], role_labels: ["Parent"] });
    const channels = {
      channels: [
        { channel: "email", label: "Email", on: true, available: true, to: "su•••@example.com" },
        { channel: "sms", label: "SMS", on: true, available: true, to: "••••••0001" },
        { channel: "whatsapp", label: "WhatsApp", on: true, available: false, to: "••••••0001" },
      ],
    };
    const calls = mockApi((method, path, body) => {
      if (path === "/auth/me") return { status: 200, body: parent };
      if (path === "/parent/children")
        return { status: 200, body: [{ id: "c1", name: "Rohan Patil", prn: "x", class: "", status: "active", relation: "Father", photo_url: null, access: { fees: true, attendance: true, results: true } }] };
      if (path === "/me/notifications" && method === "GET") return { status: 200, body: channels };
      if (path === "/me/notifications") return { status: 200, body: { channels: channels.channels.map((c) => ({ ...c, on: (body as Record<string, boolean>)[c.channel] })) } };
      return { status: 200, body: [] };
    });
    renderApp("/app/account");
    expect(await screen.findByRole("heading", { name: "कॉलेज से संदेश" })).toBeTruthy();
    expect((screen.getByLabelText(/WhatsApp/) as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/SMS/));
    fireEvent.click(screen.getByRole("button", { name: "सहेजें" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ email: true, sms: false, whatsapp: true }));
  });

  it("office sees the log and sends the queue now", async () => {
    const office = makeMe({ roles: ["office"], role_labels: ["Office"], permissions: ["messages.read"] });
    let waiting = 3;
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: office };
      if (path.startsWith("/messages/log"))
        return {
          status: 200,
          body: {
            available: { email: true, sms: false, whatsapp: false },
            waiting,
            templates: { results_published: "Results published" },
            messages: [{ at: "2026-10-05T04:00:00Z", to_name: "Rohan Patil", to: "ro•••@example.com", template: "results_published", template_label: "Results published", channel: "email", status: "failed", error: "Email service refused the message", student_id: "s1" }],
          },
        };
      if (path === "/messages/queue/run") {
        waiting = Math.max(0, waiting - 2);
        return { status: 200, body: { processed: 2, sent: 2, waiting } };
      }
      return { status: method === "GET" ? 404 : 200 };
    });
    renderApp("/app/messages");
    expect(await screen.findByText("Email service refused the message")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Send now" }));
    expect(await screen.findByText("Sent 4 messages.")).toBeTruthy();
    expect(calls.filter((c) => c.path === "/messages/queue/run")).toHaveLength(2);
  });
});
