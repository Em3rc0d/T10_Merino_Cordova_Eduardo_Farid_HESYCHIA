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
    )

def split_metadata(df: pd.DataFrame):
    train = df[df["fold"].isin(range(1, 9))].copy()
    val = df[df["fold"] == 9].copy()
    test = df[df["fold"] == 10].copy()
    return train, val, test

def assert_no_leakage(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame):
    # fsID identifies the source Freesound recording. No source recording may
    # appear across these experiment partitions.
    sets = {
        "train": set(train["fsID"].astype(int)),
        "val": set(val["fsID"].astype(int)),
        "test": set(test["fsID"].astype(int)),
    }
    if sets["train"] & sets["val"]:
        raise ValueError("fsID leakage between train and validation")
    if sets["train"] & sets["test"]:
        raise ValueError("fsID leakage between train and test")
    if sets["val"] & sets["test"]:
        raise ValueError("fsID leakage between validation and test")
