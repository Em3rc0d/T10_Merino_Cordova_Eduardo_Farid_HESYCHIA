"""Static scientific figures from frozen results; no synthetic/illustrative values."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    report = json.loads(a.report.read_text())
    rows = [r for r in report["summaries"] if "class_swapped" not in r["method"] and "M2_gate" not in r["method"]]
    a.out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                          "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(10, 6))
    ymax = max(2., max(r["A_protected_db"]["ci95"][1] for r in rows if r.get("A_protected_db")) + .3)
    ax.fill_between([6, 13], -.2, 1, color="#dcefe7", zorder=0)
    ax.axvline(6, color="#26826b", ls="--", lw=1)
    ax.axhline(1, color="#26826b", ls="--", lw=1)
    for i, row in enumerate(rows):
        target, voice = row.get("A_target_db"), row.get("A_protected_db")
        if target is None or voice is None:
            continue
        x, y = target["group_mean"], voice["group_mean"]
        xerr = [[max(0., x - target["ci95"][0])], [max(0., target["ci95"][1] - x)]]
        yerr = [[max(0., y - voice["ci95"][0])], [max(0., voice["ci95"][1] - y)]]
        label = row["method"].replace("cnn_", "").replace("_composite_class", "")
        if row["seed"] is not None:
            label += f" s{row['seed']}"
        ax.errorbar(x, y, xerr=xerr, yerr=yerr, fmt="o", ms=5, capsize=2, label=label)
    ax.set(xlim=(-.2, 13), ylim=(-.2, ymax), xlabel="Atenuación del objetivo (dB): mayor es mejor",
           ylabel="Atenuación de voz (dB): menor es mejor",
           title="Selectividad sobre grabaciones no usadas en entrenamiento")
    ax.text(6.15, .3, "Región de criterios medios", color="#1d6653", fontsize=9)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.02, 1))
    ax.grid(alpha=.15)
    fig.text(.1, .015, "Puntos: medias por grupo; barras: IC 95%. Dos ejes con grupos distintos.\n"
             "Cumplir en promedio no equivale a cumplimiento conjunto por escena. Pseudo-stems candidatos.", fontsize=8)
    fig.tight_layout(rect=(0, .065, 1, 1))
    fig.savefig(a.out / "selectivity.png", dpi=180)
    fig.savefig(a.out / "selectivity.svg")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, max(4, .36 * len(rows))))
    labels, values = [], []
    for row in rows:
        label = row["method"].replace("cnn_", "")
        if row["seed"] is not None:
            label += f" s{row['seed']}"
        labels.append(label)
        values.append(100 * (row["joint_pass_rate"] or 0))
    ax.barh(labels, values, color="#247d87")
    for idx, row in enumerate(rows):
        ax.text(values[idx] + .5, idx, f"{row['joint_pass']}/{row['joint_eligible']}", va="center", fontsize=8)
    ax.invert_yaxis()
    ax.set(xlim=(0, 110), xlabel="Escenas que cumplen ambos criterios (%)",
           title="A_target ≥ 6 dB y A_protected ≤ 1 dB, simultáneamente")
    ax.grid(axis="x", alpha=.15)
    fig.tight_layout()
    fig.savefig(a.out / "joint_success.png", dpi=180)
    fig.savefig(a.out / "joint_success.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
