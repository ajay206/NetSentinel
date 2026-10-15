import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { PqcStatus } from "./PqcStatus";
import type { PqcStatusResponse } from "../types.pqc";

const data: PqcStatusResponse = {
  checkedAt: "2026-10-15T09:00:00+00:00",
  report: "docs/pqc_report.md",
  model: {
    status: "pass",
    reason: "ok",
    alg: "ML-DSA-65",
    policy: "enforce",
    modelVersion: "v1",
  },
  tls: [
    {
      service: "llm-gateway",
      tls: true,
      hybrid: true,
      classical: false,
      hybridOnly: true,
      group: "X25519MLKEM768",
    },
    {
      service: "ml-service",
      tls: false,
      hybrid: false,
      hybridOnly: false,
      group: null,
    },
  ],
};

describe("PqcStatus", () => {
  it("shows hybrid group, plaintext services, model verify and report link", () => {
    render(<PqcStatus data={data} />);
    const rows = screen.getAllByTestId("pqc-row");
    expect(
      within(rows[0]).getByText("hybrid only · X25519MLKEM768"),
    ).toBeInTheDocument();
    expect(
      within(rows[1]).getByText("plaintext (compose network)"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("pqc-model")).toHaveTextContent(
      "pass · ML-DSA-65",
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "https://github.com/ajay206/NetSentinel/blob/main/docs/pqc_report.md",
    );
  });

  it("flags a failed verify and a classical downgrade", () => {
    render(
      <PqcStatus
        data={{
          ...data,
          model: { status: "fail", reason: "digest mismatch: model.json" },
          tls: [
            {
              ...data.tls[0],
              hybrid: true,
              classical: true,
              hybridOnly: false,
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("pqc-model")).toHaveTextContent("fail");
    const chip = screen.getByTestId("pqc-model");
    const tipId = chip.getAttribute("aria-describedby");
    expect(tipId).toBeTruthy();
    expect(document.getElementById(tipId!)).toHaveTextContent(
      "digest mismatch: model.json",
    );
    expect(
      screen.getByText("hybrid · classical still accepted"),
    ).toBeInTheDocument();
  });

  it("shows errors", () => {
    render(<PqcStatus error={new Error("pqc status 503")} />);
    expect(screen.getByText("pqc status 503")).toBeInTheDocument();
  });
});
