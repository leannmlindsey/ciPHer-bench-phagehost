#!/usr/bin/env bash
#SBATCH --job-name=phagehost_smoke
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gpus-per-node=1
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --output=logs/smoke.%j.out
#SBATCH --error=logs/smoke.%j.err

# Submit FIRST. Verifies env, conda, torch+lightgbm, ESM-2 download,
# data layout, and presence of upstream model checkpoints.
# Submit:
#   source phagehost.env
#   sbatch --account="${ACCOUNT}" --partition="${PARTITION}" \
#          --gpus-per-node="${GPUS_PER_NODE}" delta/00_smoke_test.sbatch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ ! -f "${REPO_ROOT}/phagehost.env" ]]; then
    echo "FAIL: ${REPO_ROOT}/phagehost.env missing." >&2
    echo "  cp config/phagehost_delta.env phagehost.env first." >&2
    exit 1
fi
# shellcheck disable=SC1091
source "${REPO_ROOT}/phagehost.env"

mkdir -p "${REPO_ROOT}/logs"

echo "============================================================"
echo "PhageHost smoke test"
echo "  hostname    : $(hostname)"
echo "  cpu arch    : $(uname -m)"
echo "============================================================"

echo
echo "[1/4] Conda activation"
if [[ -z "${CONDA_EXE:-}" ]] && command -v conda >/dev/null 2>&1; then
    CONDA_EXE="$(command -v conda)"
fi
if [[ -z "${CONDA_EXE:-}" ]]; then
    echo "  FAIL: conda not found. Install Miniforge first (see SETUP.md)." >&2
    exit 1
fi
# shellcheck disable=SC1091
source "$(dirname "${CONDA_EXE}")/../etc/profile.d/conda.sh"
conda activate "${PHAGEHOST_CONDA_ENV}"
echo "  active env: ${CONDA_DEFAULT_ENV}"
echo "  python:     $(python --version 2>&1)"

echo
echo "[2/4] Library check"
python <<'PY'
import sys
fails = []
for pkg in ["torch", "transformers", "lightgbm", "Bio", "pandas", "numpy", "tqdm", "sklearn"]:
    try:
        m = __import__(pkg if pkg != "Bio" else "Bio")
        ver = getattr(m, "__version__", "n/a")
        print(f"  OK  {pkg:14} {ver}")
    except Exception as e:
        print(f"  FAIL {pkg:14} {e}")
        fails.append(pkg)
if fails:
    sys.exit(2)
import torch
print(f"  CUDA available     : {torch.cuda.is_available()}")
PY

echo
echo "[3/4] Data layout"
: "${PHAGEHOST_DATA_DIR:?phagehost.env broken}"
echo "  PHAGEHOST_DATA_DIR  = ${PHAGEHOST_DATA_DIR}"
echo "  PHAGEHOST_REPO      = ${PHAGEHOST_REPO}"
echo "  CIPHER_REPO         = ${CIPHER_REPO}"
echo "  CIPHER_VAL_GENOMES  = ${CIPHER_VAL_GENOMES}"

declare -a checks=(
    "${PHAGEHOST_REPO}/model_checkpoints"
    "${PHAGEHOST_REPO}/TailSeek.py"
    "${PHAGEHOST_REPO}/data/Klebsiella_k_locus_primary_reference.csv"
    "${CIPHER_REPO}/data/validation_data/metadata/validation_rbps_all.faa"
    "${CIPHER_VAL_GENOMES}/Wang/PhageHost/predictions/tail_fiber_prediction.csv"
)
for f in "${checks[@]}"; do
    if [[ -e "${f}" ]]; then
        echo "  OK : ${f}"
    else
        echo "  FAIL: missing ${f}" >&2
        exit 3
    fi
done

echo
echo "  per-dataset Kleborate output availability:"
for ds in CHEN GORODNICHIV PBIP UCSD PhageHostLearn Beamud Ferriol Wang; do
    KLEB="${CIPHER_VAL_GENOMES}/${ds}/kleborate_out"
    if [[ -d "${KLEB}" ]] && [[ -n "$(ls "${KLEB}" 2>/dev/null)" ]]; then
        echo "    [present]  ${ds}"
    else
        echo "    [missing]  ${ds}  — OOD on ${ds} will fail until Kleborate is run"
    fi
done

echo
echo "[4/4] HostBuster model load + ESM-2 weights check"
python <<'PY'
import pickle, os
from pathlib import Path
model_pkl = Path(os.environ["PHAGEHOST_REPO"]) / "model_checkpoints" / "HostBuster_model_noM6.pkl"
print(f"  loading {model_pkl}...")
with open(model_pkl, "rb") as fh:
    m = pickle.load(fh)
print(f"  OK — HostBuster model loaded: {type(m).__name__}")

from transformers import AutoTokenizer, AutoModel
ESM2 = "facebook/esm2_t33_650M_UR50D"
print(f"  loading ESM-2 tokenizer + model...")
tok = AutoTokenizer.from_pretrained(ESM2)
model = AutoModel.from_pretrained(ESM2)
print(f"  OK — ESM-2 650M loaded ({sum(p.numel() for p in model.parameters())/1e6:.1f}M params)")
PY

echo
echo "All smoke checks passed."
