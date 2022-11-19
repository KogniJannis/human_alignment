#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import random
import warnings
from typing import Any, List, Tuple

import numpy as np
import pandas as pd
import torch
from ml_collections import config_dict
from thingsvision import get_extractor
from thingsvision.core.extraction import center_features
from thingsvision.core.rsa import compute_rdm, correlate_rdms
from thingsvision.core.rsa.helpers import correlation_matrix, cosine_matrix
from thingsvision.utils.data import DataLoader
from tqdm import tqdm

import utils
from data import DATASETS, load_dataset

FrozenDict = Any
Tensor = torch.Tensor
Array = np.ndarray


def parseargs():
    parser = argparse.ArgumentParser()

    def aa(*args, **kwargs):
        parser.add_argument(*args, **kwargs)

    aa("--data_root", type=str, help="path/to/things")
    aa("--dataset", type=str, help="Which dataset to use", choices=DATASETS)
    aa("--category", type=str, default=None,
        choices=["animals", "automobiles", "fruits", "furniture", "various", "vegetables"],
        help="Similarity judgments of the dataset from Peterson et al. (2016) were collected for inidivdual categories",
    )
    aa("--model_names", type=str, nargs="+",
        help="models for which we want to extract featues")
    aa("--module", type=str, choices=["logits", "penultimate"],
        help="module for which to extract features")
    aa("--overall_source", type=str, default="thingsvision")
    aa("--sources", type=str, nargs="+",
        choices=[
            "custom",
            "timm",
            "torchvision",
            "vissl",
            ],
        help="Source of (pretrained) models",
        )
    aa("--model_dict_path", type=str,
        default="/home/space/datasets/things/model_dict.json",
        help="Path to the model_dict.json"
        )
    aa("--input_dim", type=int, default=224, help="input image dimensionality")
    aa("--batch_size", metavar="B", type=int, default=118,
        help="number of images sampled during each step (i.e., mini-batch size)")
    aa("--out_path", type=str,
        default="/home/space/datasets/things/results/",
        help="path/to/results")
    aa("--device", type=str, default="cuda",
        help="whether evaluation should be performed on CPU or GPU (i.e., CUDA).")
    aa("--num_threads", type=int, default=4,
        help="number of threads used for intraop parallelism on CPU; use only if device is CPU")
    aa("--rnd_seed", type=int, default=42,
        help="random seed for reproducibility of results")
    aa("--verbose", action="store_true",
        help="whether to show print statements about model performance during training")
    aa("--not_pretrained",  action="store_true",
        help="load random model instead of pretrained")
    args = parser.parse_args()
    return args


def get_module_names(model_config, models: List[str], module: str) -> List[str]:
    """Get original module names for logits or penultimate layer."""
    module_names = []
    for model in models:
        try:
            module_name = model_config[model][module]["module_name"]
            module_names.append(module_name)
        except KeyError:
            raise Exception(
                f"\nMissing module name for {model}. Check config file and add module name.\nAborting evaluation run...\n"
            )
    return module_names


def get_temperatures(
    model_config, models: List[str], module: str, objective: str = "cosine"
) -> List[str]:
    """Get optimal temperature values for all models."""
    temperatures = []
    for model in models:
        try:
            t = model_config[model][module]["temperature"][objective]
        except KeyError:
            t = 1.0
            warnings.warn(
                f"\nMissing temperature value for {model} and {module} layer.\nSetting temperature value to 1.\n"
            )
        temperatures.append(t)
    return temperatures


def create_config_dicts(args) -> Tuple[FrozenDict, FrozenDict]:
    """Create data and model config dictionaries."""
    model_config = utils.evaluation.load_model_config(args.model_dict_path)
    model_cfg = config_dict.ConfigDict()
    data_cfg = config_dict.ConfigDict()
    model_cfg.names = args.model_names
    model_cfg.modules = get_module_names(model_config, model_cfg.names, args.module)
    model_cfg.temperatures = get_temperatures(
        model_config, model_cfg.names, args.module
    )
    model_cfg.sources = args.sources
    model_cfg.input_dim = args.input_dim
    model_cfg = config_dict.FrozenConfigDict(model_cfg)
    data_cfg.root = args.data_root
    data_cfg.name = args.dataset
    data_cfg.category = args.category
    data_cfg = config_dict.FrozenConfigDict(data_cfg)
    return model_cfg, data_cfg


def evaluate(args) -> None:
    """Perform evaluation with optimal temperature values."""
    device = torch.device(args.device)
    model_cfg, data_cfg = create_config_dicts(args)
    results = []
    model_features = dict()
    for i, (model_name, source) in tqdm(enumerate(zip(model_cfg.names, model_cfg.sources)), desc="Model"):
        
        if model_name.startswith('OpenCLIP'):
            name, variant, data = model_name.split('_')
            model_params = dict(variant=variant, dataset=data)
        elif model_name.startswith('clip'):
            name, variant = model_name.split('_')
            model_params = dict(variant=variant)
        else:
            name = model_name
            model_params = None
        
        family_name = utils.analyses.get_family_name(model_name)
        extractor = get_extractor(
            model_name=name,
            source=source,
            device=device,
            pretrained=not args.not_pretrained,
            model_parameters=model_params,
        )
        dataset = load_dataset(
            name=args.dataset,
            data_dir=data_cfg.root,
            category=data_cfg.category,
            transform=extractor.get_transformations(),
        )
        batches = DataLoader(
            dataset=dataset,
            batch_size=args.batch_size,
            backend=extractor.get_backend(),
        )
        features = extractor.extract_features(
            batches=batches,
            module_name=model_cfg.modules[i],
            flatten_acts=True,
        )
        features = center_features(features)

        if dataset == 'peterson':
            rdm_dnn = correlation_matrix(features)
            rdm_humans = dataset.get_rsm()
        else:
            rdm_dnn = compute_rdm(features, method="correlation")
            rdm_humans = dataset.get_rdm()

        spearman_rho = correlate_rdms(rdm_dnn, rdm_humans, correlation="spearman")
        pearson_corr_coef = correlate_rdms(rdm_dnn, rdm_humans, correlation="pearson")

        if args.verbose:
            print(
                f"\nModel: {model_name}, Family: {family_name}, Spearman's rho: {spearman_rho:.4f}, Pearson correlation coefficient: {pearson_corr_coef:.4f}\n"
            )
        summary = {
            "model": model_name,
            "zero-shot spearman": spearman_rho,
            "zero-shot pearson": pearson_corr_coef,
            "source": source,
            "family": family_name,
            "dataset": data_cfg.name,
            "category": data_cfg.category,
        }
        results.append(summary)
        model_features[model_name] = features

    # convert results into Pandas DataFrame
    results = pd.DataFrame(results)

    out_path = os.path.join(args.out_path, args.dataset, args.overall_source, args.module)
    if not os.path.exists(out_path):
        print("\nOutput directory does not exist...")
        print("Creating output directory to save results...\n")
        os.makedirs(out_path)

    # save dataframe to pickle to preserve data types after loading
    # load back with pd.read_pickle(/path/to/file/pkl)
    results.to_pickle(os.path.join(out_path, "results.pkl"))
    utils.evaluation.save_features(features=model_features, out_path=out_path)


if __name__ == "__main__":
    # parse arguments and set random seeds
    args = parseargs()
    np.random.seed(args.rnd_seed)
    random.seed(args.rnd_seed)
    torch.manual_seed(args.rnd_seed)
    # set number of threads used by PyTorch if device is CPU
    if args.device.lower().startswith("cpu"):
        torch.set_num_threads(args.num_threads)
    # run evaluation script
    evaluate(args)
