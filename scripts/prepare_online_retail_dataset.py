"""Convert the official UCI Online Retail XLSX download to a CSV test input."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_xlsx", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()

    dataframe = pd.read_excel(args.input_xlsx)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(args.output_csv, index=False)
    print(f"rows={len(dataframe)} columns={len(dataframe.columns)} output={args.output_csv}")


if __name__ == "__main__":
    main()
