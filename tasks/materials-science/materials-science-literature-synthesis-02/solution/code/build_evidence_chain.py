#!/usr/bin/env python3
"""Build the cross-source candidate-evidence chain figure."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


AXES = [
    "Symmetry\nvalidity",
    "Energetic\nstability",
    "Structural identity\nand novelty",
    "Synthesizability",
    "Direct laboratory\nrouting",
]

SOURCES = [
    {
        "id": "P1",
        "short": "SLayerGen",
        "evidence": ["support", "scope-limited", "scope-limited", "not tested", "not tested"],
    },
    {
        "id": "P2",
        "short": "LeMat-GenBench",
        "evidence": ["not tested", "caution", "caution", "not tested", "caution"],
    },
    {
        "id": "P3",
        "short": "Synthesizability pipeline",
        "evidence": ["not tested", "caution", "caution", "support", "caution"],
    },
    {
        "id": "P4",
        "short": "Physics-informed generation + CSP",
        "evidence": ["not tested", "caution", "caution", "not tested", "caution"],
    },
]

STATUS_ORDER = ["not tested", "caution", "scope-limited", "support"]
STATUS_VALUE = {status: idx for idx, status in enumerate(STATUS_ORDER)}
STATUS_COLOR = {
    "not tested": "#e5e7eb",
    "caution": "#d95f4b",
    "scope-limited": "#e9b949",
    "support": "#2d8a63",
}
STATUS_TEXT = {
    "not tested": "Not tested",
    "caution": "Caution",
    "scope-limited": "Scoped support",
    "support": "Support",
}


def evidence_matrix() -> np.ndarray:
    """Return the numeric matrix derived from the editable source records."""
    return np.asarray(
        [[STATUS_VALUE[value] for value in source["evidence"]] for source in SOURCES],
        dtype=float,
    )


def build_figure(output_path: str | Path) -> Path:
    """Render and save the evidence-chain figure."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    matrix = evidence_matrix()
    colors = [STATUS_COLOR[value] for value in STATUS_ORDER]
    cmap = ListedColormap(colors)

    fig, ax = plt.subplots(figsize=(13.5, 7.2), constrained_layout=False)
    fig.subplots_adjust(left=0.24, right=0.99, top=0.79, bottom=0.13)
    ax.imshow(matrix, cmap=cmap, vmin=-0.5, vmax=len(STATUS_ORDER) - 0.5, aspect="auto")

    ax.set_xticks(range(len(AXES)), AXES, fontsize=11)
    row_labels = [f'{source["id"]}  {source["short"]}' for source in SOURCES]
    ax.set_yticks(range(len(SOURCES)), row_labels, fontsize=11)
    ax.tick_params(top=True, labeltop=True, bottom=False, labelbottom=False, length=0, pad=10)

    for row, source in enumerate(SOURCES):
        for col, status in enumerate(source["evidence"]):
            foreground = "white" if status in {"support", "caution"} else "#1f2933"
            ax.text(
                col,
                row,
                STATUS_TEXT[status],
                ha="center",
                va="center",
                fontsize=10,
                fontweight="semibold",
                color=foreground,
            )

    ax.set_xticks(np.arange(-0.5, len(AXES), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(SOURCES), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        "Evidence chain for routing generated diperiodic crystals to the laboratory",
        fontsize=16,
        fontweight="bold",
        loc="left",
        pad=28,
    )
    fig.text(
        0.01,
        0.035,
        "Support is source-scoped. Caution marks adverse evidence or a required gate; "
        "not tested is absence of evidence, not evidence of failure.",
        fontsize=10,
        color="#374151",
    )
    fig.savefig(destination, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="candidate_evidence_chain.png")
    args = parser.parse_args()
    build_figure(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
