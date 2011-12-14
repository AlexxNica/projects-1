"""Prepare shRNA targets for differential expression analysis.
"""
import os
import csv
import subprocess

import yaml
import rpy2.robjects as rpy2

from bcbio.utils import file_exists, safe_makedir

def do_comparisons(count_file, config):
    for cmp_info in config["comparisons"]:
        for condition in cmp_info["conditions"]:
            out_file = noreplicate_comparison(count_file, condition,
                                              cmp_info["background"], config)
            #_add_gene_descriptions(out_file, config)

def noreplicate_comparison(count_file, condition, background, config):
    """Prepare a differential expression comparison without replicates.
    """
    cur_config, cur_config_file = _prepare_yaml_config(condition, background, config)
    _prepare_count_file(count_file, cur_config["infile"], condition, background)
    diffexp_file = "{0}-diffexp.tsv".format(cur_config["out_base"])
    if not file_exists(diffexp_file):
        subprocess.check_call(["Rscript", config["program"]["diffexp"], cur_config_file])
    return diffexp_file

def _add_gene_descriptions(in_file, config):
    """Add gene descriptions to differential expression output file.
    """
    out_file = apply("{0}-annotated{1}".format, os.path.splitext(in_file))
    if not file_exists(out_file):
        with open(in_file) as in_handle:
            with open(out_file, "w") as out_handle:
                reader = csv.reader(in_handle, dialect="excel-tab")
                writer = csv.writer(out_handle, dialect="excel-tab")
                header = reader.next()
                writer.writerow(header + ["genesymbol", "description"])
                for parts in reader:
                    symbol, descr = (_get_gene_descr(parts[-1].split(";"), config)
                                     if parts[-1] != "." else (".", "."))
                    writer.writerow(parts + [symbol, descr])
        print out_file
    return out_file

def _get_gene_descr(ens_gene_ids, config):
    """Retrieve gene descriptions from a list of ensembl gene IDs.
    """
    rpy2.r.assign("ids", rpy2.StrVector(ens_gene_ids))
    rpy2.r.assign("dataset", config["algorithm"]["biomart_dataset"])
    rpy2.r('''
    library(biomaRt)
    mart <- useMart("ensembl", dataset=dataset)
    result <- getBM(attributes=c("description", "hgnc_symbol"), filters=c("ensembl_gene_id"),
                    values=ids, mart=mart)
    desc <- result$description
    genesym <- result$hgnc_symbol
    ''')
    def _cleanup(name):
        return list(set(x for x in rpy2.r[name] if x))
    return (";".join(_cleanup("genesym")),
            ";".join(_cleanup("desc")))

def _prepare_count_file(orig_count, new_count, condition, background):
    """Prepare subset count with condition and background of interest.
    """
    with open(orig_count) as in_handle:
        reader = csv.reader(in_handle, dialect="excel-tab")
        header = reader.next()
        cond_i = header.index(condition)
        back_i = header.index(background)
        with open(new_count, "w") as out_handle:
            writer = csv.writer(out_handle)
            writer.writerow(["shrna.id", condition, background, "accession"])
            for parts in reader:
                target_id = apply("{0}:{1}-{2}".format, parts[:3])
                if (int(parts[cond_i]) + int(parts[back_i])) > 0:
                    writer.writerow([target_id, parts[cond_i], parts[back_i], parts[3]])

def _prepare_yaml_config(condition, background, config):
    """Prepare YAML configuration file for input to differential expression.
    """
    tmp_dir = safe_makedir(config["dir"]["tmp"])
    out_dir = safe_makedir(config["dir"]["expression"])
    base = "{exp}-{name}".format(exp=config["experiment_name"], name=condition)
    cur_config = {
        "infile": os.path.join(tmp_dir, "{0}-counts.csv".format(base)),
        "out_base": os.path.join(out_dir, base),
        "pval_thresh": float(config["algorithm"]["pval_thresh"]),
        "id_name": "shrna.id",
        "model": {"condition": [condition, background]}}
    top_targets = config["algorithm"].get("top_targets", None)
    if top_targets:
        cur_config["top_targets"] = int(top_targets)
    config_file = os.path.join(tmp_dir, "{0}-config.yaml".format(base))
    with open(config_file, "w") as out_handle:
        yaml.dump(cur_config, out_handle)
    return cur_config, config_file
