"""PyTorch Boilerplate Code for Accumulated Gradient Normalization.

Author:    Joeri R. Hermans
Date:      2 November 2017
"""

from torch.autograd import *
from torch.optim import *

import numpy as os
import os
import pickle
import sys
import time
import torch
import torch.distributed as dist
import torch.nn.functional as F


def main():
    """Main entry point of the distributed optimization mechanism."""
    # Fetch the settings from the arguments.
    settings = parse_arguments()
    # Check if the provided settings are valid.
    if settings['valid']:
        # Initialize the distributed backend.
        distributed_backend = settings['backend']
        master_orchestrator = settings['master']
        master_orchestrator_port = settings['master_port']
        # Obtain additional settings required for the distributed initialization.
        rank = settings['rank']
        world_size = settings['world_size']
        # Initialize the distributed process group.
        method = distributed_backend + '://' + master_orchestrator + ':' + str(master_orchestrator_port)
        dist.init_process_group(init_method=method, rank=rank, world_size=world_size, backend=distributed_backend)
        # Check if the current process is the master process.
        if is_master(rank):
            # Optimize for the master process.
            optimize_master(settings)
        else:
            # Call the optimization procedure under the specified settings.
            optimize(settings)
    else:
        # Display the usage information.
        usage()


class Model(torch.nn.Module):
    """YOUR MODEL HERE."""

    def __init__(self, num_features, num_hidden):
        super(Model, self).__init__()
        self.fc_1 = torch.nn.Linear(num_features, num_hidden)
        self.fc_2 = torch.nn.Linear(num_hidden, num_hidden)
        self.fc_3 = torch.nn.Linear(num_hidden, 1)

    def forward(self, x):
        x = F.relu(self.fc_1(x))
        x = F.relu(self.fc_2(x))
        x = F.sigmoid(self.fc_3(x))

        return x


def build_model(settings):
    """Constructs the model under the specified settings."""
    num_features = 10000
    num_hidden = 10000
    model = Model(num_features, num_hidden)

    return model


def is_master(rank):
    """Check if the process rank is the master rank (0)."""
    return rank == 0


def optimize_master(settings):
    """Optimization procedure for the master process."""
    rank = settings['rank']
    world_size = settings['world_size']
    num_iterations = settings['num_iterations']
    model = build_model(settings)
    next_rank = (rank + 1) % world_size
    previous_rank = (rank - 1) % world_size
    # Send the model to the next process.
    send_model(model, next_rank)
    for i in range(0, num_iterations - 1):
        receive_model(model, previous_rank)
        # TODO Add training.
        send_model(model, next_rank)
    # Collect the final model from the previuos rank.
    receive_model(model, previous_rank)


def optimize(settings):
    """Distributed Optimization Procedure under the specified settings."""
    rank = settings['rank']
    world_size = settings['world_size']
    num_iterations = settings['num_iterations']
    model = build_model(settings)
    next_rank = (rank + 1) % world_size
    previous_rank = (rank - 1) % world_size
    for i in range(0, num_iterations):
        receive_model(model, previous_rank)
        # TODO Add training.
        send_model(model, next_rank)


def send_model(model, destination):
    """Sends the parameterization of the model to the specified rank."""
    parameters = list(model.parameters())
    send_parameters(parameters, destination)


def send_parameters(parameters, destination):
    """Sends the parameterization to the specified rank."""
    for p in parameters:
        dist.send(p.data, destination)


def receive_model(model, source):
    """Receives the parameterization from the specified rank."""
    parameters = list(model.parameters())
    receive_parameters(parameters, source)


def receive_parameters(parameters, source):
    """Receives the parameterization from the specified source rank."""
    for p in parameters:
        dist.recv(p.data, source)


def set_parameterization(model, parameters):
    """Sets the tensors of the model to the specified set of parameters."""
    i = 0
    for p in model.parameters():
        p.data.copy_(parameters[i], async=True)
        i += i


def parse_arguments():
    """Parses the provided program arguments, and validates the types."""
    settings = {}
    valid = True
    # Obtain and store the arguments.
    store_argument_key(settings, key='--rank', store_in='rank', default=None)
    store_argument_key(settings, key='--world-size', store_in='world_size', default=None)
    store_argument_key(settings, key='--annouce-port', store_in='announce_port', default=5001)
    store_argument_key(settings, key='--communication-frequency', store_in='communication_frequency', default=15)
    store_argument_key(settings, key='--backend', store_in='backend', default='tcp')
    store_argument_key(settings, key='--master', store_in='master', default='127.0.0.1')
    store_argument_key(settings, key='--master-port', store_in='master_port', default=5000)
    store_argument_key(settings, key='--iterations', store_in='num_iterations', default=1000)
    # Validate and convert the type of the arguments.
    valid &= validate_argument_key(settings, 'rank', type='int')
    valid &= validate_argument_key(settings, 'world_size', type='int')
    valid &= validate_argument_key(settings, 'announce_port', type='int')
    valid &= validate_argument_key(settings, 'communication_frequency', type='int')
    valid &= validate_argument_key(settings, 'backend', type='string')
    valid &= validate_argument_key(settings, 'master', type='string')
    valid &= validate_argument_key(settings, 'master_port', type='int')
    valid &= validate_argument_key(settings, 'num_iterations', type='int')
    # Set the validation flag of the settings.
    settings['valid'] = valid

    return settings


def store_argument_key(settings, key, store_in, default=None):
    """Stores the value of the specfied key in the settings map under the 'store_in' key.
    Sets the default value if it is not present.
    """
    if key in sys.argv and sys.argv.index(key) + 1 < len(sys.argv):
        settings[store_in] = sys.argv[sys.argv.index(key) + 1]
    else:
        settings[store_in] = default


def validate_argument_key(settings, key, type=None):
    """Validates the type of the specified key, and converts it if necessary."""
    valid = False
    if key in settings.keys():
        try:
            # Check if any conversion needs to be done.
            if type == 'int':
                settings[key] = int(settings[key])
            elif type == 'float':
                settings[key] = float(settings[key])
            valid = True
        except:
            pass

    return valid


def usage():
    """Displays the usage message of this script."""
    options = '''\033[1mAccumulated Gradient Normalization\033[0m

\033[1mRequired Arguments:\033[0m
    --rank [int] Rank-identifier of the local optimization process.
    --world-size [int] Total number of workers involved in the optimization process.

\033[1mOptional Arguments:\033[0m
    --backend [string] PyTorch Distributed backend ('tcp', 'mpi', or 'gloo'). Default 'tcp'.
    --annouce-port [int] Port responsible for handling broadcast requests. Default 5001.
    --communication-frequency [int] Number of local iterations before announcing ready state. Default 15 Hz.
    --master-port [int] Port on which the master orchestrator will run. Default 5000.
    --master [string] IP address of the master process. Default '127.0.0.1'.
    --iterations [int] Number of local mini-batches that have to be evaluated. Default 1000.
'''
    print(options)


if __name__ == '__main__':
    main()
