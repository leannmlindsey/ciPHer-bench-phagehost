# ciPHer-bench-phagehost

Reproducible wrapper around **PhageHost** (Wang et al. 2026,
*Cell Reports* 45(4):117275, DOI 10.1016/j.celrep.2026.117275) for
evaluation on ciPHer's K. pneumoniae validation panel.

PhageHost is an ensemble of two PLM-based components:
- **TailSeek** — ESM-1b classifier flagging tail-fiber proteins in
  phage genomes
- **HostBuster** — LightGBM classifier that, given the tail-fiber
  embeddings + the host's Kleborate K-type, predicts the lytic
  interaction probability

Upstream tarball:
https://open.nmdc.cn/specail_data/phage/PhageHost.tar.gz

## What this repo contains

- `scripts/run_phagehost_inference.py` — in-distribution wrapper for
  Wang's own validation set (the paper's training data); reported as
  a sanity check, not a benchmark cell.
- `scripts/run_phagehost_ood.py` — OOD wrapper for cipher's CHEN, PHL,
  PBIP, UCSD, GORODNICHIV. Uses cipher's already-extracted RBPs +
  TailSeek + ESM-2 650M + Kleborate K-types + the bundled HostBuster
  LightGBM model.
- `predictions/cipher_rbp_vs_tailseek_overlap.tsv` — per-dataset count
  of how many of cipher's 840 extracted RBPs are also flagged as
  tail-fiber by TailSeek. (Useful sanity check for the OOD setup.)
- `config/` — env-style config templates.

## What this repo does NOT contain

- PhageHost upstream code (extracted from the NMDC tarball — see
  [SETUP.md](SETUP.md))
- TailSeek ESM-1b model checkpoints (ships in the tarball)
- HostBuster LightGBM model (ships in the tarball)
- Cipher RBP FASTAs (read from `$CIPHER_REPO/data/validation_data/...`)
- Per-dataset prediction matrices (regenerated locally; gitignored)

## Caveats

- **Wang is in-distribution.** PhageHost's HostBuster was trained on
  Wang. Reporting Wang's number as a benchmark cell would be unfair.
  We report it as a ceiling sanity-check only.
- **GORODNICHIV uses the KL23-reference workaround.** No GORODNICHIV
  host genomes are public; all 83 hosts are assumed KL23. Result is
  tie-saturated 1.000 — flagged in the cipher leaderboard.

## Quick start

```bash
git clone https://github.com/LeAnnMLindsey/ciPHer-bench-phagehost.git
cd ciPHer-bench-phagehost

cp config/phagehost.env.template phagehost.env
pico phagehost.env
source phagehost.env

# See SETUP.md for upstream download + env install
python scripts/run_phagehost_ood.py CHEN
```

See [SETUP.md](SETUP.md) for full setup.

## Citation

If you use this wrapper, please cite:
- Wang, et al. *An ensemble pipeline, PhageHost, for phage tail fiber
  discovery and accurate Klebsiella pneumoniae host prediction using
  protein language models.* Cell Reports 45(4):117275 (2026).
  https://doi.org/10.1016/j.celrep.2026.117275
- (manuscript in prep) ciPHer benchmarking paper.
