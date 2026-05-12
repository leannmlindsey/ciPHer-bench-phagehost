#!/usr/bin/env bash
# Convenience wrapper that translates a cipher dataset name (CHEN, PBIP, ...)
# into the right CLI args for run_phagehost_ood.py using the env config.
#
# Usage:
#   source phagehost.env
#   ./scripts/run_ood_by_dataset.sh CHEN
#   ./scripts/run_ood_by_dataset.sh PBIP
#   ./scripts/run_ood_by_dataset.sh GORODNICHIV     # KL23 workaround
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 DATASET" >&2
    echo "  DATASET: CHEN | PHL | PBIP | UCSD | GORODNICHIV" >&2
    exit 2
fi
DATASET="$1"

# Required env vars (sourced from phagehost.env):
: "${PHAGEHOST_REPO:?source phagehost.env first}"
: "${CIPHER_REPO:?source phagehost.env first}"
: "${CIPHER_VAL_GENOMES:?source phagehost.env first}"
: "${PHAGEHOST_OUTPUT_ROOT:?source phagehost.env first}"

OUT_DIR="${PHAGEHOST_OUTPUT_ROOT}/${DATASET}"
mkdir -p "${OUT_DIR}"

python "$(dirname "$0")/run_phagehost_ood.py" \
    --rbp_fasta         "${CIPHER_REPO}/data/validation_data/metadata/validation_rbps_all.faa" \
    --tailseek_csv      "${CIPHER_VAL_GENOMES}/Wang/PhageHost/predictions/tail_fiber_prediction.csv" \
    --phage_protein_map "${CIPHER_REPO}/data/validation_data/HOST_RANGE/${DATASET}/metadata/phage_protein_mapping.csv" \
    --kleborate_csv     "${CIPHER_VAL_GENOMES}/${DATASET}/kleborate_out/Kleborate_results.txt" \
    --kl_ref_csv        "${PHAGEHOST_REPO}/data/Klebsiella_k_locus_primary_reference.csv" \
    --kl_to_idx_csv     "${PHAGEHOST_REPO}/model_checkpoints/kl_to_kl_idx.csv" \
    --hostbuster_pkl    "${PHAGEHOST_REPO}/model_checkpoints/HostBuster_model_noM6.pkl" \
    --out_csv           "${OUT_DIR}/prediction_scores.csv"
