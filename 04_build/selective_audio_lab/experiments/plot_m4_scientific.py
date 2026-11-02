"""Static scientific figures from frozen results; no synthetic/illustrative values."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def label(row):
    names = {"unprocessed": "Entrada", "causal_minimum_statistics": "DSP causal",
             "oracle_IRM_privileged": "Oracle (stems)",
             "cnn_temporal_composite_class": "Temporal + clase",
             "cnn_temporal_mask_mse_class": "Temporal MSE",
             "cnn_temporal_composite_none": "Temporal sin clase",
             "cnn_spectral_composite_class": "Espectral + clase"}
    name = names.get(row["method"], row["method"])
    return name + (f" s{row['seed']}" if row["seed"] is not None else "")


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
    ymax = max(2., max(r["joint_condition_statistics"]["A_protected_db"]["mean"] for r in rows) + .3)
    ax.fill_between([6, 13], -.2, 1, color="#dcefe7", zorder=0)
    ax.axvline(6, color="#26826b", ls="--", lw=1)
    ax.axhline(1, color="#26826b", ls="--", lw=1)
    for i, row in enumerate(rows):
        target, voice = (row["joint_condition_statistics"].get(metric)
                         for metric in ("A_target_db", "A_protected_db"))
        if target is None or voice is None:
            continue
        x, y = target["mean"], voice["mean"]
        ax.plot(x, y, "o", ms=5, label=label(row))
    ax.set(xlim=(-.2, 13), ylim=(-.2, ymax), xlabel="Atenuación del objetivo (dB): mayor es mejor",
           ylabel="Atenuación de voz (dB): menor es mejor",
           title="Selectividad: las mismas 48 escenas con objetivo y voz, sin alerta")
    ax.text(6.15, .3, "Región de criterios medios", color="#1d6653", fontsize=9)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.02, 1))
    ax.grid(alpha=.15)
    fig.text(.1, .015, "Puntos: medias por escena en la misma población; sin intervalos de confianza.\n"
             "Cumplir en promedio no equivale a cumplimiento conjunto por escena. Pseudo-stems candidatos.", fontsize=8)
    fig.tight_layout(rect=(0, .065, 1, 1))
    fig.savefig(a.out / "selectivity.png", dpi=180)
    fig.savefig(a.out / "selectivity.svg")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, max(4, .36 * len(rows))))
    labels, values = [], []
    for row in rows:
        labels.append(label(row))
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
