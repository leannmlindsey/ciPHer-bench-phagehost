# PhageHost Delta data manifest

What needs to be on Delta before `scripts/run_phagehost_ood.py` will
succeed.

## Required: upstream PhageHost (NMDC tarball, 2.6 GB extracted)

```bash
# On Delta:
mkdir -p /projects/bfzj/llindsey1/PHI_TSP/ciPHer-comparisons/phagehost
cd       /projects/bfzj/llindsey1/PHI_TSP/ciPHer-comparisons/phagehost
wget https://open.nmdc.cn/specail_data/phage/PhageHost.tar.gz
tar xzf PhageHost.tar.gz
# Verify model_checkpoints/ and TailSeek.py are present
ls PhageHost/model_checkpoints/
```

Heads-up: the NMDC mirror is in China — the download may be slow from
Delta. If `wget` is rate-limited, alternative: download on laptop and
rsync up. The tarball is 5.8 MB (model_checkpoints + code) and extracts
to 2.6 GB (mainly Wang training data we don't need; safe to delete after
verifying the checkpoints work).

## Required: cipher already on Delta

`CIPHER_REPO=/projects/bfzj/llindsey1/PHI_TSP/ciPHer` — provides:
- `data/validation_data/metadata/validation_rbps_all.faa` (cipher's extracted RBPs)
- `data/validation_data/HOST_RANGE/<DS>/metadata/{interaction_matrix.tsv,phage_protein_mapping.csv}`

## Required: cipher per-dataset Kleborate output

PhageHost needs Kleborate K-type calls per dataset, currently on laptop:

| Dataset | Kleborate output (laptop)                                                       | Status |
|---|---|---|
| CHEN          | 280 KB | ready |
| GORODNICHIV   | 4 KB   | ready (synthetic — KL23 workaround) |
| PBIP          | 348 KB | ready |
| UCSD          | 268 KB | ready |
| PhageHostLearn| 384 KB | ready |
| Beamud / Ferriol / Wang | **missing** | not yet run |

Total transfer: ~1.3 MB. Trivial.

```bash
# From laptop, upload Kleborate output for ready datasets:
LOCAL=/Users/leannmlindsey/WORK/cipher_data/validation_genomes
DELTA=llindsey1@dt-login.delta.ncsa.illinois.edu:/projects/bfzj/llindsey1/PHI_TSP/cipher_data/validation_genomes

for ds in CHEN GORODNICHIV PBIP UCSD PhageHostLearn; do
    rsync -avz "${LOCAL}/${ds}/kleborate_out/" "${DELTA}/${ds}/kleborate_out/"
done
```

## Required: TailSeek output (one shared file)

The OOD wrapper consumes `tail_fiber_prediction.csv` produced by an
earlier TailSeek run on cipher's `validation_rbps_all.faa`:

```
/Users/leannmlindsey/WORK/cipher_data/validation_genomes/Wang/PhageHost/predictions/tail_fiber_prediction.csv
```

Small (KB). Upload to:
```
/projects/bfzj/llindsey1/PHI_TSP/cipher_data/validation_genomes/Wang/PhageHost/predictions/tail_fiber_prediction.csv
```

## SLURM template

PhageHost embeddings use ESM-2 650M (same as PhageHostLearn) → **needs GPU**.

```bash
#SBATCH --account=bfzj-dtai-gh
#SBATCH --partition=ghx4
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00

source $(conda info --base)/etc/profile.d/conda.sh
conda activate ${PHAGEHOST_CONDA_ENV}
source phagehost.env

./scripts/run_ood_by_dataset.sh CHEN
```
