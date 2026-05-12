#!/usr/bin/env bash
# Build ciPHer-bench-phagehost-data.zip from the laptop.
# Output: /Users/leannmlindsey/Desktop/ciPHer-bench-data-zips/ciPHer-bench-phagehost-data.zip
#
# Layout MIRRORS the laptop layout under data/ so that env vars
# (PHAGEHOST_REPO, CIPHER_REPO, CIPHER_VAL_GENOMES) keep working unchanged.
#
# Contents (extracts to data/ on Delta):
#   data/PhageHost/                         Extracted NMDC tarball
#                                           (TailSeek.py, model_checkpoints/,
#                                            tailseek/, data/, configs/)
#   data/cipher/data/validation_data/
#       metadata/validation_rbps_all.faa
#       HOST_RANGE/<DS>/metadata/...
#   data/cipher_val_genomes/<DS>/kleborate_out/Kleborate_results.txt
#                                           (CHEN/GORODNICHIV/PBIP/UCSD/PHL ready;
#                                            Beamud/Ferriol/Wang missing)
#   data/cipher_val_genomes/Wang/PhageHost/predictions/tail_fiber_prediction.csv
#                                           (shared across datasets)
#
# Run from the laptop.
set -euo pipefail

SRC_PHAGEHOST="/Users/leannmlindsey/WORK/cipher_data/validation_genomes/Wang/PhageHost"
SRC_CIPHER="/Users/leannmlindsey/WORK/PHI_TSP/cipher"
SRC_VAL_GENOMES="/Users/leannmlindsey/WORK/cipher_data/validation_genomes"
OUT_DIR="/Users/leannmlindsey/Desktop/ciPHer-bench-data-zips"
STAGE_PARENT="$(mktemp -d -t phagehost-data-zip-XXXXXX)"
STAGE_DIR="${STAGE_PARENT}/data"
ZIP_PATH="${OUT_DIR}/ciPHer-bench-phagehost-data.zip"

mkdir -p "${OUT_DIR}" "${STAGE_DIR}"

echo "[1/4] Upstream PhageHost (~2.6 GB extracted)"
mkdir -p "${STAGE_DIR}/PhageHost"
rsync -a --exclude '__pycache__' --exclude 'predictions' \
      --exclude '*.tar.gz' \
      "${SRC_PHAGEHOST}/" "${STAGE_DIR}/PhageHost/"

echo "[2/4] cipher mirror — validation RBPs + per-dataset metadata"
mkdir -p "${STAGE_DIR}/cipher/data/validation_data/metadata"
cp "${SRC_CIPHER}/data/validation_data/metadata/validation_rbps_all.faa" \
   "${STAGE_DIR}/cipher/data/validation_data/metadata/"
mkdir -p "${STAGE_DIR}/cipher/data/validation_data/HOST_RANGE"
for ds in CHEN GORODNICHIV PBIP UCSD PhageHostLearn; do
    SRC="${SRC_CIPHER}/data/validation_data/HOST_RANGE/${ds}/metadata"
    if [ -d "${SRC}" ]; then
        DST="${STAGE_DIR}/cipher/data/validation_data/HOST_RANGE/${ds}/metadata"
        mkdir -p "${DST}"
        cp -R "${SRC}/." "${DST}/"
    fi
done

echo "[3/4] cipher_val_genomes mirror — per-dataset Kleborate output"
mkdir -p "${STAGE_DIR}/cipher_val_genomes"
for ds in CHEN GORODNICHIV PBIP UCSD PhageHostLearn Beamud Ferriol Wang; do
    KLEB_DIR="${SRC_VAL_GENOMES}/${ds}/kleborate_out"
    if [ -d "${KLEB_DIR}" ]; then
        mkdir -p "${STAGE_DIR}/cipher_val_genomes/${ds}"
        cp -R "${KLEB_DIR}" "${STAGE_DIR}/cipher_val_genomes/${ds}/"
        echo "  cipher_val_genomes/${ds}/kleborate_out: $(du -sh "${STAGE_DIR}/cipher_val_genomes/${ds}/kleborate_out" | cut -f1)"
    else
        echo "  cipher_val_genomes/${ds}/kleborate_out: MISSING — run Kleborate first"
    fi
done

# Wang's shared TailSeek prediction file (used by all OOD runs)
TAIL_PRED="${SRC_PHAGEHOST}/predictions/tail_fiber_prediction.csv"
if [ -f "${TAIL_PRED}" ]; then
    mkdir -p "${STAGE_DIR}/cipher_val_genomes/Wang/PhageHost/predictions"
    cp "${TAIL_PRED}" "${STAGE_DIR}/cipher_val_genomes/Wang/PhageHost/predictions/"
    echo "  cipher_val_genomes/Wang/PhageHost/predictions/tail_fiber_prediction.csv: $(du -sh "${TAIL_PRED}" | cut -f1)"
fi

echo "  staged total: $(du -sh "${STAGE_DIR}" | cut -f1)"

echo "[4/4] Zip (fast compression)"
cd "${STAGE_PARENT}"
zip -qr -1 "${ZIP_PATH}" data
du -sh "${ZIP_PATH}"

rm -rf "${STAGE_PARENT}"

echo
echo "Done. Zip at: ${ZIP_PATH}"
