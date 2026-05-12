"""PhageHost (HostBuster) inference on a cipher validation dataset (OOD).

Inputs are cipher's already-extracted RBPs (validation_rbps_all.faa, per-dataset
phage_protein_mapping.csv) and Kleborate output for the dataset's host genomes.

Pipeline:
  1. Filter cipher's RBPs to this dataset's phages
  2. Use TailSeek predictions (run via TailSeek.py on validation_rbps_all.faa)
  3. ESM-2 650M mean-pool each RBP
  4. Build PhageHost input dataframe (ORFname, predicted_p_true, embedding, phage_name)
  5. Convert Kleborate output to per-host KL_onehot + KL_genes feature
  6. Build (phage, host) pairs and run HostBuster
"""
import argparse, math, pickle, sys
from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModel
from Bio import SeqIO


def build_host_features(kleborate_path, kl_ref_csv, kl_to_idx_csv):
    """Mirrors PH_inference.ipynb cells 14-19."""
    kp = pd.read_csv(kleborate_path, sep="\t")
    if "strain" in kp.columns:
        kp = kp.set_index("strain")
    col_missing = ("K_Missing_expected_genes" if "K_Missing_expected_genes" in kp.columns
                   else "K_locus_missing_genes")
    kp.fillna({col_missing: ""}, inplace=True)
    kl_ref = pd.read_csv(kl_ref_csv)
    feats = kp[["K_locus"]].copy()
    feats["K_locus"] = feats["K_locus"].apply(
        lambda x: x.split(" ")[1].strip("()") if isinstance(x, str) and "unknown" in x else x)
    feats = feats.rename(columns={"K_locus": "KL"})
    kl_to_idx = pd.read_csv(kl_to_idx_csv, index_col=0, header=0)["0"].to_dict()
    feats["KL_int"] = feats["KL"].map(kl_to_idx, na_action="ignore")
    feats.fillna({"KL_int": len(kl_to_idx)}, inplace=True)
    feats["KL_int"] = feats["KL_int"].astype(int)
    feats["KL_onehot"] = feats["KL_int"].apply(
        lambda x: np.concatenate([np.eye(len(kl_to_idx), dtype=int),
                                  np.zeros((1, len(kl_to_idx)), dtype=int)], axis=0)[x])
    gene_table = kl_ref["locus_tag"].str.split("_", expand=True, n=2)
    gene_table.columns = ["KL", "gene_pos", "gene_name"]
    gene_table["count"] = 1
    gene_table = gene_table.pivot_table(index="KL", columns="gene_name", values="count",
                                        aggfunc="sum", fill_value=0)
    known = feats["KL"].isin(gene_table.index)
    feats = feats[known].copy()
    gt = gene_table.loc[feats.KL].reset_index(drop=True)
    gt.index = feats.index
    gtv = deepcopy(gt)
    for s in gtv.index:
        miss = kp.loc[s, col_missing]
        mg = [t.strip().split("_")[-1] for t in miss.split(",", 2)] if miss else []
        for g in mg:
            if g in gtv.columns and gtv.loc[s, g] > 0:
                gtv.loc[s, g] -= 1
    feats["KL_genes"] = gtv.values.tolist()
    feats["KL_genes"] = feats["KL_genes"].apply(np.array)
    return feats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rbp_fasta", required=True,
                    help="cipher's validation_rbps_all.faa")
    ap.add_argument("--tailseek_csv", required=True,
                    help="TailSeek output: ORFname,seq,logits,predicted_p_true,...")
    ap.add_argument("--phage_protein_map", required=True,
                    help="cipher's per-dataset phage_protein_mapping.csv")
    ap.add_argument("--kleborate_csv", required=True)
    ap.add_argument("--kl_ref_csv", required=True)
    ap.add_argument("--kl_to_idx_csv", required=True)
    ap.add_argument("--hostbuster_pkl", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--esm2_emb_csv", default=None,
                    help="Optional pre-computed ESM-2 650M embedding CSV (rows: protein_id, then 1280 floats)")
    args = ap.parse_args()

    print("[1] Load cipher RBPs + filter to this dataset's phages", flush=True)
    ppm = pd.read_csv(args.phage_protein_map)
    keep = set(ppm["protein_id"])
    print(f"  this dataset has {len(keep)} cipher RBPs across {ppm['matrix_phage_name'].nunique()} phages")

    seqs = {}
    for r in SeqIO.parse(args.rbp_fasta, "fasta"):
        if r.id in keep:
            seqs[r.id] = str(r.seq).strip("*")
    print(f"  matched in FASTA: {len(seqs)}")

    print("\n[2] Load TailSeek predictions", flush=True)
    ts = pd.read_csv(args.tailseek_csv)
    ts = ts[ts["ORFname"].isin(keep)].copy()
    ts = ts.set_index("ORFname")
    print(f"  matched TailSeek rows: {len(ts)}")

    print("\n[3] Load or compute ESM-2 650M embeddings", flush=True)
    if args.esm2_emb_csv and Path(args.esm2_emb_csv).exists():
        emb_df = pd.read_csv(args.esm2_emb_csv, index_col=0, header=None)
        emb_df = emb_df.loc[[k for k in emb_df.index if k in keep]]
        print(f"  loaded {len(emb_df)} pre-computed embeddings")
    else:
        print("  computing ESM-2 650M embeddings (this is the slow step)", flush=True)
        tok = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
        model = AutoModel.from_pretrained("facebook/esm2_t33_650M_UR50D").to("cpu")
        model.eval()
        embs = {}
        for pid, seq in seqs.items():
            ids = tok(seq, return_tensors="pt", truncation=True, max_length=1024).to("cpu")
            with torch.no_grad():
                out = model(**ids)
            h = out.last_hidden_state[0, 1:-1, :]
            embs[pid] = h.mean(dim=0).cpu().numpy()
        emb_df = pd.DataFrame(embs).T

    print("\n[4] Build phage proteins dataframe (PhageHost input format)", flush=True)
    pid_to_phage = dict(zip(ppm["protein_id"], ppm["matrix_phage_name"]))
    phage_proteins = pd.DataFrame({
        "ORFname": [k for k in emb_df.index if k in ts.index],
    })
    phage_proteins["phage_name"] = phage_proteins["ORFname"].map(pid_to_phage)
    phage_proteins["predicted_p_true"] = phage_proteins["ORFname"].map(ts["predicted_p_true"].to_dict())
    phage_proteins["embedding"] = phage_proteins["ORFname"].apply(
        lambda k: torch.from_numpy(emb_df.loc[k].values.astype(np.float32)))
    phage_proteins = phage_proteins.dropna(subset=["phage_name", "predicted_p_true"])
    print(f"  phage_proteins rows: {len(phage_proteins)} across {phage_proteins['phage_name'].nunique()} phages")

    print("\n[5] Build host features from Kleborate", flush=True)
    kp_feats = build_host_features(args.kleborate_csv, args.kl_ref_csv, args.kl_to_idx_csv)
    print(f"  host features: {len(kp_feats)} hosts (with KL known by kleborate)")

    print("\n[6] Build (phage, host) pairs + features", flush=True)
    pairs = pd.DataFrame({"phage_name": phage_proteins.phage_name.unique()})\
              .merge(pd.DataFrame({"genome_id": kp_feats.index.unique()}), how="cross")

    # phage features = top-3 by predicted_p_true, mean-pool
    top_k = 3
    phage_emb = phage_proteins.groupby("phage_name").apply(
        lambda g: torch.stack(list(g.loc[g["predicted_p_true"].sort_values(ascending=False).index[:top_k]]["embedding"]), dim=0).mean(dim=0),
        include_groups=False)
    phage_min = phage_proteins.groupby("phage_name").apply(
        lambda g: g["predicted_p_true"].sort_values(ascending=False).iloc[:top_k].min(),
        include_groups=False)
    phage_mean = phage_proteins.groupby("phage_name").apply(
        lambda g: g["predicted_p_true"].sort_values(ascending=False).iloc[:top_k].mean(),
        include_groups=False)
    phage_df = pd.DataFrame({"embedding": phage_emb, "min_p_true": phage_min, "mean_p_true": phage_mean})

    pairs["features"] = pairs.apply(
        lambda row: torch.cat([phage_df.loc[row.phage_name]["embedding"],
                               torch.tensor(kp_feats.loc[row.genome_id]["KL_onehot"]),
                               torch.tensor(kp_feats.loc[row.genome_id]["KL_genes"])], dim=0),
        axis=1).reset_index(drop=True)

    print("\n[7] HostBuster predict", flush=True)
    hb = pickle.load(open(args.hostbuster_pkl, "rb"))
    pairs["predicted_p_lysed"] = hb.predict(np.stack(pairs["features"].values))
    pivot = pairs.pivot(index="genome_id", columns="phage_name", values="predicted_p_lysed")
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    pivot.to_csv(args.out_csv)
    print(f"  -> {args.out_csv}  shape {pivot.shape}")
    print(f"  scores  min={pivot.values.min():.4f}  max={pivot.values.max():.4f}  mean={pivot.values.mean():.4f}")


if __name__ == "__main__":
    main()
