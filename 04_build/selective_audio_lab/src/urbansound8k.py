from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

EXPECTED_CLASSES = {
    0: "air_conditioner",
    1: "car_horn",
    2: "children_playing",
    3: "dog_bark",
    4: "drilling",
    5: "engine_idling",
    6: "gun_shot",
    7: "jackhammer",
    8: "siren",
    9: "street_music",
}
EXPECTED_FOLDS = set(range(1, 11))
EXPECTED_ROWS = 8732
REQUIRED_COLUMNS = {
    "slice_file_name",
    "fsID",
    "start",
    "end",
    "salience",
    "fold",
    "classID",
    "class",
}


@dataclass(frozen=True)
class DatasetContractReport:
    rows: int
    folds: tuple[int, ...]
    classes: tuple[str, ...]
    missing_audio: int
    official_shape_ok: bool
    filename_metadata_consistency_ok: bool
    occurrence_fold_consistency_ok: bool
    cross_fold_occurrence_count: int
    cross_fold_occurrence_sample: tuple[str, ...]
    cross_fold_fsid_count: int
    cross_fold_fsid_sample: tuple[int, ...]
    cross_fold_fsid_cross_class_only: bool


def metadata_path(root: str | Path) -> Path:
    return Path(root) / "metadata" / "UrbanSound8K.csv"


def audio_path(root: str | Path, fold: int, filename: str) -> Path:
    return Path(root) / "audio" / f"fold{fold}" / filename


def _filename_parts(filename: str) -> tuple[int, int, int, int]:
    stem = Path(str(filename)).stem
    parts = stem.split("-")
    if len(parts) != 4:
        raise ValueError(
            f"Unexpected UrbanSound8K filename format: {filename!r}"
        )
    try:
        fsid, class_id, occurrence_id, slice_id = map(int, parts)
    except ValueError as exc:
        raise ValueError(
            f"Non-numeric UrbanSound8K filename token: {filename!r}"
        ) from exc
    return fsid, class_id, occurrence_id, slice_id


def _with_occurrence_columns(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    parsed = enriched["slice_file_name"].map(_filename_parts)
    enriched["_filename_fsid"] = parsed.map(lambda x: x[0])
    enriched["_filename_class_id"] = parsed.map(lambda x: x[1])
    enriched["_occurrence_id"] = parsed.map(lambda x: x[2])
    enriched["_slice_id"] = parsed.map(lambda x: x[3])
    enriched["_occurrence_key"] = (
        enriched["_filename_fsid"].astype(str)
        + ":"
        + enriched["_filename_class_id"].astype(str)
        + ":"
        + enriched["_occurrence_id"].astype(str)
    )
    return enriched


def load_metadata(root: str | Path) -> pd.DataFrame:
    path = metadata_path(root)
    if not path.exists():
        raise FileNotFoundError(
            f"UrbanSound8K metadata not found: {path}. "
            "Expected <root>/metadata/UrbanSound8K.csv"
        )
    df = pd.read_csv(path)
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing metadata columns: {sorted(missing_cols)}")
    df = df.copy()
    df["fold"] = df["fold"].astype(int)
    df["classID"] = df["classID"].astype(int)
    df["fsID"] = df["fsID"].astype(int)
    return df


def source_fold_violations(df: pd.DataFrame) -> pd.DataFrame:
    """Diagnostic only: fsIDs allocated to more than one official fold.

    UrbanSound8K v1.0 contains a small number of cross-fold fsIDs where the
    same Freesound source contributes different target classes. The official
    folds must not be rewritten to "fix" those cases.
    """
    grouped = (
        df.assign(fsID=df["fsID"].astype(int), fold=df["fold"].astype(int))
        .groupby("fsID")["fold"]
        .agg(lambda s: tuple(sorted(set(int(x) for x in s))))
    )
    bad = grouped[grouped.map(len) > 1]
    return bad.rename("folds").reset_index()


def occurrence_fold_violations(df: pd.DataFrame) -> pd.DataFrame:
    """Return labeled sound occurrences whose slices cross official folds.

    Filename contract:
    [fsID]-[classID]-[occurrenceID]-[sliceID].wav

    This is the unit that must remain grouped for slice-level leakage control.
    """
    enriched = _with_occurrence_columns(df)
    grouped = (
        enriched.groupby("_occurrence_key")["fold"]
        .agg(lambda s: tuple(sorted(set(int(x) for x in s))))
    )
    bad = grouped[grouped.map(len) > 1]
    return bad.rename("folds").reset_index()


def filename_metadata_violations(df: pd.DataFrame) -> pd.DataFrame:
    enriched = _with_occurrence_columns(df)
    return enriched[
        (enriched["_filename_fsid"] != enriched["fsID"].astype(int))
        | (enriched["_filename_class_id"] != enriched["classID"].astype(int))
    ].copy()


def validate_contract(
    root: str | Path,
    *,
    require_official_shape: bool = True,
    verify_audio: bool = True,
) -> DatasetContractReport:
    df = load_metadata(root)
    folds = set(df["fold"].unique().tolist())
    class_pairs = {
        int(cid): str(name)
        for cid, name in df[["classID", "class"]]
        .drop_duplicates()
        .itertuples(index=False)
    }

    if not folds.issubset(EXPECTED_FOLDS):
        raise ValueError(f"Unexpected folds: {sorted(folds - EXPECTED_FOLDS)}")
    for cid, name in class_pairs.items():
        expected = EXPECTED_CLASSES.get(cid)
        if expected is None or expected != name:
            raise ValueError(f"Unexpected class mapping: {cid} -> {name!r}")

    if require_official_shape:
        if len(df) != EXPECTED_ROWS:
            raise ValueError(f"Expected {EXPECTED_ROWS} rows, found {len(df)}")
        if folds != EXPECTED_FOLDS:
            raise ValueError(f"Expected folds 1..10, found {sorted(folds)}")
        if class_pairs != EXPECTED_CLASSES:
            raise ValueError("Class map does not match official UrbanSound8K")

    filename_bad = filename_metadata_violations(df)
    occurrence_bad = occurrence_fold_violations(df)
    fsid_bad = source_fold_violations(df)

    cross_fold_fsid_cross_class_only = True
    if not fsid_bad.empty:
        for fsid in fsid_bad["fsID"].astype(int):
            rows = df[df["fsID"].astype(int) == fsid]
            if rows["classID"].nunique() <= 1:
                cross_fold_fsid_cross_class_only = False
                break

    missing_audio = 0
    if verify_audio:
        for row in df.itertuples(index=False):
            if not audio_path(
                root, int(row.fold), str(row.slice_file_name)
            ).exists():
                missing_audio += 1
        if missing_audio:
            raise FileNotFoundError(
                f"{missing_audio} audio files referenced by metadata are missing"
            )

    return DatasetContractReport(
        rows=len(df),
        folds=tuple(sorted(folds)),
        classes=tuple(sorted(set(df["class"].astype(str)))),
        missing_audio=missing_audio,
        official_shape_ok=(
            len(df) == EXPECTED_ROWS
            and folds == EXPECTED_FOLDS
            and class_pairs == EXPECTED_CLASSES
        ),
        filename_metadata_consistency_ok=filename_bad.empty,
        occurrence_fold_consistency_ok=occurrence_bad.empty,
        cross_fold_occurrence_count=int(len(occurrence_bad)),
        cross_fold_occurrence_sample=tuple(
            str(x) for x in occurrence_bad["_occurrence_key"].head(10).tolist()
        ),
        cross_fold_fsid_count=int(len(fsid_bad)),
        cross_fold_fsid_sample=tuple(
            int(x) for x in fsid_bad["fsID"].head(10).tolist()
        ),
        cross_fold_fsid_cross_class_only=cross_fold_fsid_cross_class_only,
    )


def split_metadata(df: pd.DataFrame):
    train = df[df["fold"].isin(range(1, 9))].copy()
    val = df[df["fold"] == 9].copy()
    test = df[df["fold"] == 10].copy()
    return train, val, test


def _occurrence_keys(df: pd.DataFrame) -> set[str]:
    return set(_with_occurrence_columns(df)["_occurrence_key"].astype(str))


def assert_no_leakage(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
):
    """Block leakage of slices from the same labeled occurrence.

    The official UrbanSound8K v1.0 archive contains a small number of fsIDs
    that occur in multiple folds for different classes. Reassigning official
    folds would violate the dataset protocol, so fsID overlap is reported as a
    diagnostic but is not used as the blocking key. The blocking unit is the
    labeled occurrence (fsID, classID, occurrenceID).
    """
    frames = {
        "train": train,
        "validation": val,
        "test": test,
    }
    keys = {name: _occurrence_keys(frame) for name, frame in frames.items()}
    pairs = (
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
    )
    failures = []
    for left, right in pairs:
        overlap = sorted(keys[left] & keys[right])
        if overlap:
            failures.append(
                f"{left}<->{right}: count={len(overlap)}, "
                f"sample={overlap[:10]}"
            )
    if failures:
        raise ValueError(
            "labeled-occurrence leakage detected. " + " | ".join(failures)
        )
