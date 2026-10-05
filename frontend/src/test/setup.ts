import { beforeEach } from "vitest";
import { resetLanguageForTests } from "../lib/language";
import { resetOfflineForTests } from "../lib/offline";

// The chosen language is shared app-wide state; start every test from what localStorage says.
beforeEach(() => {
  resetLanguageForTests();
  resetOfflineForTests();
});
