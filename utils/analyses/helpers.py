#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import warnings
from functools import partial
from typing import List

import numpy as np
import pandas as pd

from .families import Families

Array = np.ndarray


def aggregate_dimensions(concept_embedding: Array, idx_triplet: Array) -> Array:
    """Aggregate the histogram of dimensions across the pair of the two most similar objects."""
    triplet_embedding = concept_embedding[idx_triplet]
    pair_dimensions = triplet_embedding[:-1].mean(axis=0)
    return pair_dimensions


def get_max_dims(concept_embedding: Array, triplets: Array) -> Array:
    """Get most important dimension for the most similar object pair in a triplet."""
    aggregate = partial(aggregate_dimensions, concept_embedding)

    def get_max_dim(triplet: Array) -> Array:
        pair_dimensions = aggregate(triplet)
        return np.argmax(pair_dimensions)

    return np.apply_along_axis(get_max_dim, axis=1, arr=triplets)


def get_topk_dims(concept_embedding: Array, triplets: Array, k: int = 2) -> Array:
    """Get top-k most important dimension for the most similar object pair in a triplet."""
    aggregate = partial(aggregate_dimensions, concept_embedding)

    def get_topks(k: int, triplet: Array) -> Array:
        aggregated_dimensions = aggregate(triplet)
        return np.argsort(-aggregated_dimensions)[:k]

    return np.apply_along_axis(partial(get_topks, k), axis=1, arr=triplets).flatten()


def get_failures(triplets: Array, model_choices: Array, target: int = 2) -> Array:
    """Partition triplets into failure and correctly predicted triplets."""
    model_failures = np.where(model_choices != target)[0]
    failure_triplets = triplets[model_failures]
    return failure_triplets


def get_family_name(model_name: str) -> str:
    families = Families([model_name])
    all_children = [attr for attr in dir(families) if attr.endswith("children")]
    for children in all_children:
        if getattr(families, children):
            family_name = families.mapping[children]
            if not family_name == "CNN" or family_name == "SSL":
                break
    return family_name


def merge_results(
    root: str, model_sources: List[str], dataset: str, layer: str
) -> pd.DataFrame:
    results = []
    for source in model_sources:
        results_path = os.path.join(root, dataset, source, layer)
        try:
            source_results = get_results(results_path)
        except FileNotFoundError:
            warnings.warn(
                f"\nCould not find any results for source: <{source}> and layer: <{layer}>.\n"
            )
            continue
        if "source" not in source_results.columns.values:
            source_results["source"] = source
        results.append(source_results)
    results = pd.concat(results, axis=0, ignore_index=True)
    return results


def get_results(root: str) -> pd.DataFrame:
    return pd.read_pickle(os.path.join(root, "results.pkl"))
