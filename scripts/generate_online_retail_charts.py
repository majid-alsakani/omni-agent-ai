"""Create reproducible visuals from the official UCI Online Retail CSV test input."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


INPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/uci-online-retail/online_retail.csv")
OUTPUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("artifacts/online_retail_visuals.png")


def main() -> None:
    dataframe = pd.read_csv(INPUT, low_memory=False)
    dataframe["InvoiceDate"] = pd.to_datetime(dataframe["InvoiceDate"], errors="coerce")
    dataframe["Quantity"] = pd.to_numeric(dataframe["Quantity"], errors="coerce").fillna(0)
    dataframe["UnitPrice"] = pd.to_numeric(dataframe["UnitPrice"], errors="coerce").fillna(0)
    dataframe["Revenue"] = dataframe["Quantity"] * dataframe["UnitPrice"]
    cancelled = dataframe["InvoiceNo"].astype("string").str.casefold().str.startswith("c", na=False)
    completed = dataframe.loc[~cancelled].copy()

    daily = completed.groupby(completed["InvoiceDate"].dt.date)["Revenue"].sum()
    top_countries = completed.groupby("Country")["Revenue"].sum().sort_values().tail(8)

    plt.style.use("dark_background")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5), facecolor="#070914")
    for axis in axes:
        axis.set_facecolor("#10162e")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=0.15)

    axes[0].plot(daily.index, daily.values, color="#60d7ff", linewidth=1.6)
    axes[0].fill_between(daily.index, daily.values, color="#6d4df5", alpha=0.25)
    axes[0].set_title("Completed Retail Revenue by Day", loc="left", fontsize=14, fontweight="bold")
    axes[0].set_ylabel("Revenue (GBP)")
    axes[0].tick_params(axis="x", rotation=35, labelsize=8)

    bars = axes[1].barh(top_countries.index, top_countries.values, color="#a78bfa")
    axes[1].set_title("Top Markets by Completed Revenue", loc="left", fontsize=14, fontweight="bold")
    axes[1].set_xlabel("Revenue (GBP)")
    for bar, value in zip(bars, top_countries.values):
        axes[1].text(value, bar.get_y() + bar.get_height() / 2, f"  {value:,.0f}", va="center", fontsize=8, color="#dbeafe")

    fig.suptitle("UCI Online Retail — Omni-Agent Data Analysis Lab", x=0.02, ha="left", fontsize=18, fontweight="bold", color="#eef1ff")
    fig.text(0.02, 0.01, "Source: UCI Online Retail | Completed invoices only; cancellations excluded from chart series.", color="#93a0c4", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight")


if __name__ == "__main__":
    main()
