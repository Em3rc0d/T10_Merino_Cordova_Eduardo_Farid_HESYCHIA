"""M4 scientific candidate: prepare -> train -> freeze -> evaluate -> predict."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from m4_scientific.common import read_json, sha256, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--root", default="data/m4_sci")
    prep.add_argument("--speech-per-speaker", type=int, default=4)
    prep.add_argument("--counts", nargs=3, type=int, default=[1600, 160, 160])
    prep.add_argument("--seconds", type=float, default=2.)
    prep.add_argument("--workers", type=int, default=6)
    train = sub.add_parser("train")
    train.add_argument("--root", default="data/m4_sci")
    train.add_argument("--config", default="configs/m4_sci_candidate.json")
    train.add_argument("--out", required=True)
    train.add_argument("--seed", type=int)
    train.add_argument("--loss", choices=("composite", "mask_mse"))
    train.add_argument("--conditioning", choices=("class", "none"))
    train.add_argument("--pilot-unreviewed", action="store_true")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--root", default="data/m4_sci")
    freeze.add_argument("--checkpoints", nargs="+", required=True)
    freeze.add_argument("--out", required=True)
    freeze.add_argument("--event-checkpoint")
    freeze.add_argument("--event-calibration")
    events = sub.add_parser("train-events")
    events.add_argument("--root", default="data/m4_sci")
    events.add_argument("--out", required=True)
    events.add_argument("--epochs", type=int, default=20)
    events.add_argument("--pilot-unreviewed", action="store_true")
    validation = sub.add_parser("validate")
    validation.add_argument("--root", default="data/m4_sci")
    validation.add_argument("--checkpoints", nargs="+", required=True)
    validation.add_argument("--out", required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--root", default="data/m4_sci")
    evaluate.add_argument("--freeze", required=True)
    evaluate.add_argument("--out", required=True)
    predict = sub.add_parser("predict")
    predict.add_argument("--checkpoint", required=True)
    predict.add_argument("--input", required=True)
    predict.add_argument("--out", required=True)
    predict.add_argument("--target", choices=("vacuum_cleaner", "chainsaw"), required=True)
    predict.add_argument("--block-protected", action="store_true")
    predict.add_argument("--event-checkpoint")
    predict.add_argument("--event-calibration")
    args = p.parse_args()
    if args.action == "prepare":
        from m4_scientific.corpus import prepare, load_registry
        from m4_scientific.scenes import save_recipes
        audit = prepare(args.root, speech_per_speaker=args.speech_per_speaker, workers=args.workers)
        registry = load_registry(args.root, allow_unreviewed=True)
        recipes = save_recipes(args.root, registry, counts=tuple(args.counts), seconds=args.seconds)
        result = dict(audit=audit, recipes=recipes)
    elif args.action == "train":
        from m4_scientific.training import fit
        cfg = read_json(args.config)
        for key in ("seed", "loss", "conditioning"):
            if getattr(args, key) is not None:
                cfg[key] = getattr(args, key)
        result = fit(args.root, args.out, cfg, pilot_unreviewed=args.pilot_unreviewed)
    elif args.action == "freeze":
        from m4_scientific.evaluation import freeze
        result = freeze(args.root, args.checkpoints, args.out,
                        event_checkpoint=args.event_checkpoint, event_calibration=args.event_calibration)
    elif args.action == "train-events":
        from m4_scientific.events import fit_events
        result = fit_events(args.root, args.out, epochs=args.epochs, pilot_unreviewed=args.pilot_unreviewed)
    elif args.action == "validate":
        from m4_scientific.validation import validate_candidates
        result = validate_candidates(args.root, args.checkpoints, args.out)
    elif args.action == "evaluate":
        from m4_scientific.evaluation import evaluate
        result = evaluate(args.root, args.freeze, args.out)
    else:
        from m4_scientific.inference import predict_file
        result = predict_file(args.checkpoint, args.input, args.out, args.target,
                              block_protected=args.block_protected,
                              event_checkpoint=args.event_checkpoint, event_calibration=args.event_calibration)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
