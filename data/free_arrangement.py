#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
from typing import Any

import numpy as np
import torch
from PIL import Image
from scipy.io import loadmat

Tensor = torch.Tensor
Array = np.ndarray


class FreeArrangement(torch.utils.data.Dataset):
    def __init__(
        self,
        root: str,
        stimulus_set: str = "set1",
        transform=None,
        target_transform=None,
    ) -> None:
        super(FreeArrangement, self).__init__()
        self.root = root
        self.img_subfolder = "images"
        self.sim_subfolder = "sim_judgements"
        self.stimulus_set = stimulus_set
        self.transform = transform
        self.target_transform = target_transform
        self.order = sorted(
            [
                f.name
                for f in os.scandir(
                    os.path.join(self.root, self.img_subfolder, self.stimulus_set)
                )
                if f.name.endswith("jpg")
            ]
        )
        sim_judgments = self.load_sim_judgments()
        self.pairwise_dists = self.get_pairwise_distances(sim_judgments)

    def load_sim_judgments(self) -> Any:
        sim_judgements = loadmat(
            os.path.join(self.root, self.sim_subfolder, "BEHAVIOR.mat")
        )
        return sim_judgements

    def get_pairwise_distances(self, sim_judgments: Any):
        pairwise_distances = sim_judgments["BEHAVIOR"][self.stimulus_set][0, 0][
            "pairwisedistances"
        ][0, 0]
        pairwise_distances = pairwise_distances.mean(axis=0)
        return pairwise_distances

    def __getitem__(self, idx: int) -> Tensor:
        img = os.path.join(self.root, self.img_subfolder, self.order[idx])
        img = Image.open(img)
        if self.transform is not None:
            img = self.transform(img)
        return img

    def __len__(self) -> int:
        return len(self.order)
