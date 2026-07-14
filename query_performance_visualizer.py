from __future__ import annotations

import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_seconds(value: object) -> float:
    """Convert strings such as '0.3s', '1m 3s', or '7m 6s' to seconds."""
    text = str(value).strip().lower()
    minutes = 0.0
    seconds = 0.0

    minute_match = re.search(r"([\d.]+)\s*m", text)
    second_match = re.search(r"([\d.]+)\s*s", text)

    if minute_match:
        minutes = float(minute_match.group(1))
    if second_match:
        seconds = float(second_match.group(1))

    if not minute_match and not second_match:
        return float(text)

    return minutes * 60 + seconds


def parse_megabytes(value: object) -> float:
    """Convert values such as '341.41 MB' to a float in megabytes."""
    text = str(value).strip()
    match = re.search(r"([\d.]+)", text.replace(",", ""))
    if not match:
        raise ValueError(f"Could not parse file size: {value!r}")
    return float(match.group(1))


def parse_integer(value: object) -> int:
    """Convert spreadsheet values with commas or non-breaking spaces to int."""
    text = str(value).replace(",", "").replace("\xa0", "").strip()
    return int(float(text))


def load_data(workbook: Path) -> pd.DataFrame:
    df = pd.read_excel(workbook)

    required = {
        "image count",
        "model",
        "created statements",
        "file size",
        "query time",
        "GraphDB query optimization iteration",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["image count"] = df["image count"].astype(int)
    df["model"] = df["model"].astype(str)
    df["created statements"] = df["created statements"].map(parse_integer)
    df["file size MB"] = df["file size"].map(parse_megabytes)
    df["query time seconds"] = df["query time"].map(parse_seconds)
    df["optimizer iterations"] = df[
        "GraphDB query optimization iteration"
    ].map(parse_integer)

    return df.sort_values(["image count", "model"])


def save_figure(output_dir: Path, filename: str) -> None:

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir , f"{filename}.png"), dpi=300, bbox_inches="tight")
    plt.close()


def plot_query_time(df: pd.DataFrame, output_dir: Path) -> None:
    pivot = df.pivot(index="image count", columns="model", values="query time seconds")

    plt.figure(figsize=(7.2, 4.8))
    for model in pivot.columns:
        plt.plot(
            pivot.index,
            pivot[model],
            marker="o",
            linewidth=2,
            label=model,
        )

    plt.xscale("log")
    plt.xlabel("Number of images")
    plt.ylabel("Query execution time (seconds)")
    plt.title("Query execution time by dataset size")
    plt.grid(True, alpha=0.3)
    plt.legend(title="Model")
    save_figure(output_dir, "query_execution_time")


def plot_file_size(df: pd.DataFrame, output_dir: Path) -> None:
    pivot = df.pivot(index="image count", columns="model", values="file size MB")
    ax = pivot.plot(kind="bar", figsize=(7.2, 4.8))

    ax.set_xlabel("Number of images")
    ax.set_ylabel("Repository file size (MB)")
    ax.set_title("Repository size by dataset and modeling approach")
    ax.legend(title="Model")
    ax.tick_params(axis="x", rotation=0)
    ax.grid(axis="y", alpha=0.3)
    save_figure(output_dir, "repository_size")


def plot_statement_count(df: pd.DataFrame, output_dir: Path) -> None:
    pivot = df.pivot(
        index="image count",
        columns="model",
        values="created statements",
    )
    ax = pivot.plot(kind="bar", figsize=(7.2, 4.8))

    ax.set_xlabel("Number of images")
    ax.set_ylabel("Number of created statements")
    ax.set_title("Statement count by dataset and modeling approach")
    ax.legend(title="Model")
    ax.tick_params(axis="x", rotation=0)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    save_figure(output_dir, "statement_count")
    plt.close()


def plot_optimizer_iterations(df: pd.DataFrame, output_dir: Path) -> None:
    pivot = df.pivot(
        index="image count",
        columns="model",
        values="optimizer iterations",
    )

    plt.figure(figsize=(7.2, 4.8))
    for model in pivot.columns:
        plt.plot(
            pivot.index,
            pivot[model],
            marker="o",
            linewidth=2,
            label=model,
        )

    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Number of images")
    plt.ylabel("Estimated optimizer iterations")
    plt.title("GraphDB optimizer workload by dataset size")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend(title="Model")
    save_figure(output_dir, "optimizer_iterations")


def plot_import_time(df: pd.DataFrame, output_dir: Path) -> None:
    parsed = df.copy()
    parsed["import time seconds"] = parsed["import time"].map(parse_seconds)

    pivot = parsed.pivot(
        index="image count",
        columns="model",
        values="import time seconds",
    )
    ax = pivot.plot(kind="bar", figsize=(7.2, 4.8))

    ax.set_xlabel("Number of images")
    ax.set_ylabel("Import time (seconds)")
    ax.set_title("GraphDB import time by dataset size")
    ax.legend(title="Model")
    ax.tick_params(axis="x", rotation=0)
    ax.grid(axis="y", alpha=0.3)
    save_figure(output_dir, "import_time")


if __name__ == '__main__':

    excel_file = "query_speed.xlsx"
    df = load_data(excel_file)
    output_dir = os.path.join(os.getcwd(), "vis_pics")
    plot_query_time(df, output_dir)
    plot_file_size(df, output_dir)
    plot_statement_count(df, output_dir)
    plot_optimizer_iterations(df, output_dir)



