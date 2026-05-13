# Setup + reproduce

## Workflow at a glance

```text
1. (on laptop) build data zip      → ciPHer-bench-phagehost-data.zip
2. (on laptop) rsync zip to Delta
3. (on Delta) unzip into data/
4. (on Delta) source phagehost.env, build conda env, run wrappers
```

## 1. Build the data zip on the laptop

```bash
cd /Users/leannmlindsey/Desktop/ciPHer-bench-staging/ciPHer-bench-phagehost
bash build_data_zip.sh
# Output: /Users/leannmlindsey/Desktop/ciPHer-bench-data-zips/ciPHer-bench-phagehost-data.zip
```

Layout mirrors the laptop tree:
- `data/PhageHost/` — extracted NMDC tarball (TailSeek.py + model_checkpoints)
- `data/cipher/data/validation_data/...` — cipher's metadata mirror
- `data/cipher_val_genomes/<DS>/kleborate_out/` — per-dataset Kleborate output
  **(CHEN/GORODNICHIV/PBIP/UCSD/PhageHostLearn ready; Beamud/Ferriol/Wang missing)**
- `data/cipher_val_genomes/Wang/PhageHost/predictions/tail_fiber_prediction.csv`
  — shared TailSeek output for all OOD runs

## 2. Transfer + unzip on Delta

```bash
ZIP=/Users/leannmlindsey/Desktop/ciPHer-bench-data-zips/ciPHer-bench-phagehost-data.zip
rsync -avz --info=progress2 "${ZIP}" \
    llindsey1@dt-login.delta.ncsa.illinois.edu:/projects/bfzj/llindsey1/PHI_TSP/ciPHer-comparisons/phagehost/data/

ssh llindsey1@dt-login.delta.ncsa.illinois.edu
cd /projects/bfzj/llindsey1/PHI_TSP/ciPHer-comparisons/phagehost

git clone git@github.com:LeAnnMLindsey/ciPHer-bench-phagehost.git .   # first time
cd data && unzip -q ciPHer-bench-phagehost-data.zip && cd ..
```

## 3. Build the conda env

```bash
# Conda must be available; install Miniforge to project space if not:
#   wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh
#   bash Miniforge3-Linux-$(uname -m).sh -b -p /projects/bfzj/llindsey1/miniforge3
#   source /projects/bfzj/llindsey1/miniforge3/etc/profile.d/conda.sh

conda env create -f environment.yml
conda activate phagehost

# If the upstream PhageHost ships extra requirements you need:
# pip install -r "${PHAGEHOST_REPO}/requirements.txt"
```

## 4. Configure paths + run

```bash
cp config/phagehost_delta.env phagehost.env
source phagehost.env

# Verify:
ls "${PHAGEHOST_REPO}/model_checkpoints/"   # should not be empty

# OOD on each cipher dataset:
./scripts/run_ood_by_dataset.sh CHEN
./scripts/run_ood_by_dataset.sh PBIP
./scripts/run_ood_by_dataset.sh UCSD
./scripts/run_ood_by_dataset.sh GORODNICHIV    # tie-saturated (KL23 workaround)
./scripts/run_ood_by_dataset.sh PHL
```

Or in sbatch:

```bash
#!/usr/bin/env bash
#SBATCH --job-name=phagehost_chen
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x.%j.out
source $(conda info --base)/etc/profile.d/conda.sh
conda activate phagehost
source phagehost.env
./scripts/run_ood_by_dataset.sh CHEN
```
