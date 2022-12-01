#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   run.py
@Contact :   xansar@ruc.edu.cn

@Modify Time      @Author    @Version    @Desciption
------------      -------    --------    -----------
2022/10/26 16:22   zxx      1.0         None
"""

import os
import json

import torch
import numpy as np

import argparse
import random

from dataset import *
from metric import *
from model import *
from trainer import *

from configparser import ConfigParser

CommonModel = ['MF', 'AA', 'Node2Vec']
GCNModel = ['LightGCN', 'TrustSVD', 'SVDPP', 'Sorec', 'MutualRec', 'FusionLightGCN', 'DiffnetPP', 'GraphRec', 'SocialMF']

use_common_datset = ['LightGCN', 'MF']
use_social_dataset = ['MutualRec', 'FusionLightGCN', 'DiffnetPP', 'GraphRec', 'AA', 'Node2Vec']
use_directed_social_dataset = ['TrustSVD', 'SVDPP', 'Sorec', 'SocialMF']

class MyConfigParser(ConfigParser):
    def __init__(self, defaults=None):
        super(MyConfigParser, self).__init__()

    def optionxform(self, optionstr):
        return optionstr

def setup_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)


def parse_args():
    # Parses the arguments.
    parser = argparse.ArgumentParser(description="Run Model.")
    parser.add_argument('-m', '--model', type=str, default='DiffnetPP',
                        help='Choose config')
    parser.add_argument('-v', '--visulize', type=bool, default=False,
                        help='whether to visulize train logs with tensorboard')
    parser.add_argument('-d', '--dataset', type=str, default=None,
                        help='choose dataset')
    return parser.parse_args()

def get_config(args):
    config = MyConfigParser()
    model = args.model
    config.read('./config/' + model + '.ini', encoding='utf-8')
    config = config._sections

    if args.dataset is None:
        data_name = config['DATA']['data_name']
    else:
        data_name = args.dataset
    data_info = get_data_info(data_name)
    config['DATA']['data_name'] = data_name
    config['MODEL'].update(data_info)

    config.update({'VISUALIZED': args.visulize})
    return config

def get_data_info(data_name):
    fp = os.path.join('./data/', data_name, 'behavior_data/data_info.json')
    with open(fp, 'r') as f:
        data_info = json.load(f)
    return data_info

def run():
    args = parse_args()
    config = get_config(args)

    seed = eval(config['TRAIN']['random_seed'])

    # 随机抽seed
    # seed = random.randint(0, 145161)
    # config['TRAIN']['random_seed'] = str(seed)

    setup_seed(seed)

    model_name = config['MODEL']['model_name']
    task = config['TRAIN']['task']

    if model_name in use_common_datset:
        dataset = DGLRecDataset(config, use_social=False)
    else:
        if model_name in use_social_dataset:
            dataset = DGLRecDataset(config, use_social=True, directed=False)
        elif model_name in use_directed_social_dataset:
            dataset = DGLRecDataset(config, use_social=True, directed=True)
        else:
            raise ValueError("Wrong Model Name!!!")

    if model_name in CommonModel:
        model = eval(model_name + 'Model')(config)
    elif model_name in GCNModel:
        etype = dataset[0].etypes
        model = eval(model_name + 'Model')(config, etype)
    else:
        raise ValueError("Wrong Model Name!!!")
    # model.apply(weight_init)

    # optimizer
    optimizer_name = 'torch.optim.' + config['OPTIM']['optimizer']
    if 'embedding_weight_decay' in config['OPTIM'].keys():
        optimizer_grouped_params = [
            {'params': [p for n, p in model.named_parameters() if 'embeds' in n],
             'lr': eval(config['OPTIM']['embedding_learning_rate']),
             'weight_decay': eval(config['OPTIM']['embedding_weight_decay'])
             },
            {'params': [p for n, p in model.named_parameters() if 'embeds' not in n],
             'lr': eval(config['OPTIM']['learning_rate']),
             'weight_decay': eval(config['OPTIM']['weight_decay'])
             }
        ]
        optimizer = eval(optimizer_name)(params=optimizer_grouped_params)
    else:
        lr = eval(config['OPTIM']['learning_rate'])
        weight_decay = eval(config['OPTIM']['weight_decay'])
        optimizer = eval(optimizer_name)(lr=lr, params=model.parameters(), weight_decay=weight_decay)


    lr_scheduler_name = 'torch.optim.lr_scheduler.' + config['OPTIM']['lr_scheduler']
    T_0 = eval(config['OPTIM']['T_0'])  # 学习率第一次重启的epoch数
    T_mult = eval(config['OPTIM']['T_mult'])    # 学习率衰减epoch数变化倍率
    lr_scheduler = eval(lr_scheduler_name)(optimizer, T_0=T_0, T_mult=T_mult, verbose=True)
    # loss func
    loss_name = config['LOSS']['loss_name']
    loss_func = eval(loss_name)(reduction='mean')
    # metric

    metric = BaseMetric(config)
    # trainer
    trainer = eval(model_name + 'Trainer')(
        model=model,
        loss_func=loss_func,
        optimizer=optimizer,
        lr_scheduler=lr_scheduler,
        metric=metric,
        dataset=dataset,
        config=config
    )
    trainer.train()


if __name__ == '__main__':
    run()
    # model_name = ['LightGCN', 'FusionLightGCN']
    # for n in model_name:
    #     config_pth = 'Ciao' + n + '.ini'
    #     for i in range(1):
    #         run(config_pth, True)

