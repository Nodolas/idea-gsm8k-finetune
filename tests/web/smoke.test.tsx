import { renderPage, screen } from "@/test/utils";

describe("website test harness", () => {
  it("setup renders the landing route", async () => {
    renderPage("/");
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(document.querySelector("main#main")).not.toBeNull();
  });
});
