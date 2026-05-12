# Setup + reproduce

## 1. Download upstream PhageHost tarball

```bash
# Wherever PHAGEHOST_REPO in your env points (you may need to mkdir its
# parent first):
mkdir -p "$(dirname "$PHAGEHOST_REPO")"
cd       "$(dirname "$PHAGEHOST_REPO")"
wget https://open.nmdc.cn/specail_data/phage/PhageHost.tar.gz
tar xzf PhageHost.tar.gz
# This produces a PhageHost/ directory; rename if your env var
# expects a different leaf:
# mv PhageHost "$(basename "$PHAGEHOST_REPO")"
```

The tarball ships:
- `TailSeek.py` + `tailseek/` — ESM-1b based tail-fiber detector
- `model_checkpoints/` — pre-trained weights (HostBuster + TailSeek)
- `data/` — Wang's training data
- `PH_inference.ipynb` — the original notebook

## 2. Build the conda env

```bash
conda create -n phagehost python=3.10 -y
conda activate phagehost
pip install -r "$PHAGEHOST_REPO/requirements.txt"
# Plus the deps used by the OOD wrapper:
pip install transformers torch lightgbm biopython pandas tqdm scikit-learn
```

## 3. Install Kleborate (for K-type calls on cipher OOD hosts)

```bash
brew tap brewsci/bio
brew install mash minimap2
pip install kleborate
kleborate --help
```

(macOS-specific; on Linux clusters use `conda install -c bioconda mash minimap2 kleborate`.)

## 4. Configure paths

```bash
cp config/phagehost.env.template phagehost.env   # laptop
# or:
cp config/phagehost_delta.env    phagehost.env
cp config/phagehost_biowulf.env  phagehost.env

pico phagehost.env
source phagehost.env

echo "PHAGEHOST_REPO=$PHAGEHOST_REPO"
echo "CIPHER_REPO=$CIPHER_REPO"
echo "CIPHER_VAL_GENOMES=$CIPHER_VAL_GENOMES"
ls "$PHAGEHOST_REPO/model_checkpoints/"           # should not be empty
```

## 5. Run OOD on cipher datasets

```bash
source phagehost.env
python scripts/run_phagehost_ood.py CHEN
python scripts/run_phagehost_ood.py PBIP
python scripts/run_phagehost_ood.py UCSD
python scripts/run_phagehost_ood.py GORODNICHIV    # KL23 workaround
python scripts/run_phagehost_ood.py PHL
```

Each run writes a prediction matrix CSV under
`$PHAGEHOST_OUTPUT_ROOT/<dataset>/`.

## 6. (Optional) Wang in-distribution sanity check

```bash
source phagehost.env
python scripts/run_phagehost_inference.py
```

The number this produces should match what's reported in the
Wang Cell Reports paper. If it doesn't, the env vars or upstream
checkpoints are wrong.
