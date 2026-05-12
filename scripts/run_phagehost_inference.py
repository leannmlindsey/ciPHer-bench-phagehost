"""PhageHost (HostBuster) inference on a dataset.

Mirrors PH_inference.ipynb. Inputs:
  - phage_pkl: DataFrame {ORFname, predicted_p_true, embedding, phage_name}
  - kleborate_csv: kleborate output (must contain K_locus + K_locus_missing_genes or K_Missing_expected_genes)
  - kl_ref_gene_csv: Klebsiella_k_locus_primary_reference.csv (defines K-locus gene table)
  - kl_to_kl_idx_csv: model_checkpoints/kl_to_kl_idx.csv (KL → integer one-hot index)
  - hostbuster_pkl: model_checkpoints/HostBuster_model_noM6.pkl (LightGBM)

Filters to a subset of phages / hosts if provided; default = all.

Outputs:
  - {out_dir}/prediction_scores.csv: rows=hosts, cols=phages, values=p_lysed (cipher format)
"""
import argparse, math, pickle, sys
from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import torch


def prepare_data_for_fitting(df_pairs, df_kp, df_phage_protein,
                             top_k_protein=3, square_normalize=False):
    """Mirrors PH_inference.ipynb Cell 22."""
    all_data = deepcopy(df_pairs)
    phage_embedding = df_phage_protein.groupby('phage_name').apply(
        lambda g: torch.stack(list(
            g.loc[g['predicted_p_true'].sort_values(ascending=False).index[:top_k_protein]]['embedding']
        ), dim=0).mean(dim=0) * (math.sqrt(min(len(g), top_k_protein)) if square_normalize else 1.0),
        include_groups=False,
    )
    phage_k_picked = df_phage_protein.groupby('phage_name').apply(
        lambda g: min(top_k_protein, g.shape[0]), include_groups=False)
    phage_min_p_true = df_phage_protein.groupby('phage_name').apply(
        lambda g: g['predicted_p_true'].sort_values(ascending=False).iloc[:top_k_protein].min(),
        include_groups=False)
    phage_mean_p_true = df_phage_protein.groupby('phage_name').apply(
        lambda g: g['predicted_p_true'].sort_values(ascending=False).iloc[:top_k_protein].mean(),
        include_groups=False)
    phage_df = pd.DataFrame({'embedding': phage_embedding,
                              'n_taillike_proteins': phage_k_picked,
                              'min_p_true': phage_min_p_true,
                              'mean_p_true': phage_mean_p_true})
    all_data['features'] = all_data.apply(
        lambda row: torch.cat([
            phage_df.loc[row['phage_name']]['embedding'],
            torch.tensor(df_kp.loc[row['genome_id']]['KL_onehot']),
            torch.tensor(df_kp.loc[row['genome_id']]['KL_genes']),
        ], dim=0),
        axis=1)
    return all_data.reset_index(drop=True)


def build_host_features(kleborate_csv, kl_ref_gene_csv, kl_to_kl_idx_csv):
    """Mirrors PH_inference.ipynb Cells 14-19."""
    kp = pd.read_csv(kleborate_csv, index_col=0)
    if 'strain' in kp.columns:
        kp = kp.set_index('strain')
    col_missing = ('K_Missing_expected_genes' if 'K_Missing_expected_genes' in kp.columns
                   else 'K_locus_missing_genes')
    kp.fillna({col_missing: ''}, inplace=True)

    kl_ref = pd.read_csv(kl_ref_gene_csv)

    feats = kp[['K_locus']].copy()
    feats['K_locus'] = feats['K_locus'].apply(
        lambda x: x.split(' ')[1].strip("()") if isinstance(x, str) and 'unknown' in x else x)
    feats = feats.rename(columns={'K_locus': 'KL'})

    kl_to_kl_idx = pd.read_csv(kl_to_kl_idx_csv, index_col=0, header=0)['0'].to_dict()
    feats['KL_int_label'] = feats['KL'].map(kl_to_kl_idx, na_action='ignore')
    feats.fillna({'KL_int_label': len(kl_to_kl_idx)}, inplace=True)
    feats['KL_int_label'] = feats['KL_int_label'].astype(int)
    feats['KL_onehot'] = feats['KL_int_label'].apply(
        lambda x: np.concatenate([np.eye(len(kl_to_kl_idx), dtype=int),
                                  np.zeros((1, len(kl_to_kl_idx)), dtype=int)], axis=0)[x])

    kl_gene_table = kl_ref['locus_tag'].str.split('_', expand=True, n=2)
    kl_gene_table.columns = ['KL', 'gene_position', 'gene_name']
    kl_gene_table['count'] = 1
    kl_gene_table = kl_gene_table.pivot_table(index='KL', columns='gene_name', values='count',
                                              aggfunc='sum', fill_value=0)

    # Filter strains whose KL is known by kleborate
    known_mask = feats['KL'].isin(kl_gene_table.index)
    if not known_mask.all():
        print(f"  WARNING: {(~known_mask).sum()} strains have unknown KL types, dropping them",
              file=sys.stderr)
        feats = feats[known_mask].copy()

    gene_table = kl_gene_table.loc[feats.KL].reset_index(drop=True)
    gene_table.index = feats.index
    gene_table_v = deepcopy(gene_table)
    for strain in gene_table_v.index:
        missing = kp.loc[strain, col_missing]
        missing_genes = [s.strip().split('_')[-1] for s in missing.split(',', 2)] if missing else []
        for g in missing_genes:
            if g in gene_table_v.columns and gene_table_v.loc[strain, g] > 0:
                gene_table_v.loc[strain, g] -= 1
    feats['KL_genes'] = gene_table_v.values.tolist()
    feats['KL_genes'] = feats['KL_genes'].apply(np.array)
    return feats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phage_pkl", required=True, help="phage_protein_ts_prediction_and_esm_embedding.pkl")
    ap.add_argument("--kleborate_csv", required=True)
    ap.add_argument("--kl_ref_gene_csv", required=True)
    ap.add_argument("--kl_to_kl_idx_csv", required=True)
    ap.add_argument("--hostbuster_pkl", required=True)
    ap.add_argument("--out_csv", required=True, help="output: hosts × phages prediction matrix")
    ap.add_argument("--phage_filter_file", default=None, help="optional file with phage_ids, one per line")
    ap.add_argument("--host_filter_file", default=None, help="optional file with host_ids, one per line")
    ap.add_argument("--top_k_protein", type=int, default=3)
    args = ap.parse_args()

    print("[1] Load phage proteins + TS predictions + ESM-2 embeddings", flush=True)
    phage_proteins = pd.read_pickle(args.phage_pkl)
    print(f"  rows: {len(phage_proteins)}, unique phages: {phage_proteins['phage_name'].nunique()}")

    print("\n[2] Build host features from kleborate", flush=True)
    kp_features = build_host_features(args.kleborate_csv, args.kl_ref_gene_csv, args.kl_to_kl_idx_csv)
    print(f"  hosts after KL filtering: {len(kp_features)}")

    # Apply filters
    if args.phage_filter_file:
        keep_phages = {l.strip() for l in open(args.phage_filter_file) if l.strip()}
        phage_proteins = phage_proteins[phage_proteins['phage_name'].isin(keep_phages)]
        print(f"  filtered to {phage_proteins['phage_name'].nunique()} phages")
    if args.host_filter_file:
        keep_hosts = {l.strip() for l in open(args.host_filter_file) if l.strip()}
        kp_features = kp_features[kp_features.index.isin(keep_hosts)]
        print(f"  filtered to {len(kp_features)} hosts")

    print("\n[3] Build (phage, host) pair feature matrix", flush=True)
    phage_names = pd.DataFrame({'phage_name': phage_proteins.phage_name.unique()})
    host_names  = pd.DataFrame({'genome_id':  kp_features.index.unique()})
    pairs = phage_names.merge(host_names, how='cross')
    print(f"  total pairs: {len(pairs)}")

    all_data = prepare_data_for_fitting(pairs, kp_features, phage_proteins,
                                         top_k_protein=args.top_k_protein)

    print("\n[4] HostBuster predict", flush=True)
    model = pickle.load(open(args.hostbuster_pkl, "rb"))
    all_data['predicted_p_lysed'] = model.predict(np.stack(all_data['features'].values))

    pivot = all_data.pivot(index='genome_id', columns='phage_name', values='predicted_p_lysed')
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    pivot.to_csv(args.out_csv)
    print(f"  -> {args.out_csv}  shape {pivot.shape}")
    print(f"  scores  min={pivot.values.min():.4f}  max={pivot.values.max():.4f}  mean={pivot.values.mean():.4f}")
    print("Done.")


if __name__ == "__main__":
    main()
