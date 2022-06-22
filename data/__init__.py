from .things import THINGSBehavior
from .cifar import CIFAR100Triplet, CIFAR100CoarseTriplet, CIFAR10Triplet
from .things import THINGSTriplet, THINGSBehavior

DATASETS = ['cifar100-coarse', 'cifar100-fine', 'cifar10', 'things']


def load_dataset(name, data_dir, transform):
    if name == 'cifar100-coarse':
        dataset = CIFAR100CoarseTriplet(root=data_dir, train=True,
                                        download=True, transform=transform,
                                        samples=10000, seed=0)
    elif name == 'cifar100-fine':
        dataset = CIFAR100Triplet(root=data_dir, train=True,
                                  download=True, transform=transform,
                                  samples=10000, seed=0)
    elif name == 'cifar10':
        dataset = CIFAR10Triplet(root=data_dir, train=True,
                                 download=True, transform=transform,
                                 samples=10000, seed=0)
    elif name == 'things':
        dataset = THINGSBehavior(root=data_dir, download=True, transform=transform)
    else:
        raise ValueError('Unknown dataset')

    return dataset