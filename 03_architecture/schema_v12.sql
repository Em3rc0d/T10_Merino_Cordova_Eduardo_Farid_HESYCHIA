-- HESYCHIA T10 — schema v1.2
-- Evolución aditiva de v1.1 para persistir explícitamente la baseline PI8.
CREATE TABLE IF NOT EXISTS dataset(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  license TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_asset(
  id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES dataset(id),
  path TEXT NOT NULL,
  checksum TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK(role IN ('benchmark','protected','target','background')),
  split TEXT NOT NULL CHECK(split IN ('train','val','test')),
  fold INTEGER,
  sr INTEGER NOT NULL,
  duration_s REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS model_version(
  id TEXT PRIMARY KEY,
  task TEXT NOT NULL CHECK(task IN ('semantic','mask')),
  format TEXT NOT NULL CHECK(format IN ('keras','savedmodel','tflite','sklearn','baseline')),
  version TEXT NOT NULL,
  checksum TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('candidate','frozen','rejected'))
);

CREATE TABLE IF NOT EXISTS experiment(
  id TEXT PRIMARY KEY,
  scenario TEXT NOT NULL CHECK(scenario IN ('recognition','attenuation','edge')),
  config_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run(
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL REFERENCES experiment(id),
  model_version_id TEXT NOT NULL REFERENCES model_version(id),
  device TEXT NOT NULL,
  seed INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
  started_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS run_asset(
  run_id TEXT NOT NULL REFERENCES run(id),
  asset_id TEXT NOT NULL REFERENCES audio_asset(id),
  role TEXT NOT NULL CHECK(role IN ('protected','target','background','input')),
  gain_db REAL NOT NULL,
  PRIMARY KEY(run_id, asset_id, role)
);

CREATE TABLE IF NOT EXISTS policy_decision(
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run(id),
  target_label TEXT NOT NULL,
  protected_set TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('ALLOW','BLOCK')),
  reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric(
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run(id),
  family TEXT NOT NULL CHECK(family IN ('semantic','acoustic','compute')),
  name TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact(
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run(id),
  kind TEXT NOT NULL CHECK(kind IN ('audio','mask','log','config','model','report')),
  path TEXT NOT NULL,
  checksum TEXT NOT NULL
);
