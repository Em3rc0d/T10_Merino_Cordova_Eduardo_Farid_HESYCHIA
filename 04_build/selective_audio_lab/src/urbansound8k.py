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
    "slice_file_name","fsID","start","end","salience","fold","classID","class"
}

@dataclass(frozen=True)
class DatasetContractReport:
    rows: int
    folds: tuple[int, ...]
    classes: tuple[str, ...]
    missing_audio: int
    official_shape_ok: bool
    source_fold_consistency_ok: bool
    cross_fold_fsid_count: int
    cross_fold_fsid_sample: tuple[int, ...]

def metadata_path(root: str | Path) -> Path:
    return Path(root) / "metadata" / "UrbanSound8K.csv"

def audio_path(root: str | Path, fold: int, filename: str) -> Path:
    return Path(root) / "audio" / f"fold{fold}" / filename

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
    return df

def source_fold_violations(df: pd.DataFrame) -> pd.DataFrame:
    """Return fsIDs that appear in more than one official fold."""
    grouped = (
        df.assign(fsID=df["fsID"].astype(int), fold=df["fold"].astype(int))
        .groupby("fsID")["fold"]
        .agg(lambda s: tuple(sorted(set(int(x) for x in s))))
    )
    bad = grouped[grouped.map(len) > 1]
    return bad.rename("folds").reset_index()


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
        for cid, name in df[["classID", "class"]].drop_duplicates().itertuples(index=False)
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

    violations = source_fold_violations(df)
    source_fold_consistency_ok = violations.empty

    missing_audio = 0
    if verify_audio:
        for row in df.itertuples(index=False):
            if not audio_path(root, int(row.fold), str(row.slice_file_name)).exists():
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
        source_fold_consistency_ok=source_fold_consistency_ok,
        cross_fold_fsid_count=int(len(violations)),
        cross_fold_fsid_sample=tuple(
            int(x) for x in violations["fsID"].head(10).tolist()
        ),
    )

def split_metadata(df: pd.DataFrame):
    train = df[df["fold"].isin(range(1, 9))].copy()
    val = df[df["fold"] == 9].copy()
    test = df[df["fold"] == 10].copy()
    return train, val, test

def assert_no_leakage(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame):
    # fsID identifies the source Freesound recording. No source recording may
    # appear across these experiment partitions.
    frames = {"train": train, "validation": val, "test": test}
    sets = {
        name: set(frame["fsID"].astype(int))
        for name, frame in frames.items()
    }
    pairs = (
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
    )
    failures = []
    for left, right in pairs:
        overlap = sorted(sets[left] & sets[right])
        if overlap:
            details = []
            for fsid in overlap[:10]:
                fold_rows = pd.concat(
                    [
                        frames[left].loc[
                            frames[left]["fsID"].astype(int) == fsid,
                            ["fold", "slice_file_name"],
                        ],
                        frames[right].loc[
                            frames[right]["fsID"].astype(int) == fsid,
                            ["fold", "slice_file_name"],
                        ],
                    ]
                )
                folds = sorted(set(int(x) for x in fold_rows["fold"]))
                details.append(f"{fsid}:folds={folds}")
            failures.append(
                f"{left}<->{right}: count={len(overlap)}, sample=[{'; '.join(details)}]"
            )
    if failures:
        raise ValueError(
            "fsID leakage/source-fold inconsistency detected. "
            + " | ".join(failures)
        )
