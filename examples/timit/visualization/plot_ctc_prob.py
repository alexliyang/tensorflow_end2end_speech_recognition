#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Plot the trained CTC posteriors (TIMIT corpus)."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from os.path import join, abspath, isdir
import sys
import numpy as np
import tensorflow as tf
import yaml
import argparse
import shutil

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
plt.style.use('ggplot')
import seaborn as sns
sns.set_style("white")
blue = '#4682B4'
orange = '#D2691E'
green = '#006400'

sys.path.append(abspath('../../../'))
from experiments.timit.data.load_dataset_ctc import Dataset
from models.ctc.ctc import CTC
from utils.directory import mkdir_join, mkdir

parser = argparse.ArgumentParser()
parser.add_argument('--epoch', type=int, default=-1,
                    help='the epoch to restore')
parser.add_argument('--model_path', type=str,
                    help='path to the model to evaluate')
parser.add_argument('--eval_batch_size', type=str, default=1,
                    help='the size of mini-batch in evaluation')


def do_plot(model, params, epoch, eval_batch_size):
    """Plot the CTC posteriors.
    Args:
        model: the model to restore
        params (dict): A dictionary of parameters
        epoch (int): epoch to restore
        eval_batch_size (int): the size of mini-batch in evaluation
    """
    # Load dataset
    test_data = Dataset(
        data_type='test', label_type=params['label_type'],
        batch_size=eval_batch_size, splice=params['splice'],
        num_stack=params['num_stack'], num_skip=params['num_skip'],
        sort_utt=False, progressbar=True)

    # Define placeholders
    model.create_placeholders()

    # Add to the graph each operation (including model definition)
    _, logits = model.compute_loss(model.inputs_pl_list[0],
                                   model.labels_pl_list[0],
                                   model.inputs_seq_len_pl_list[0],
                                   model.keep_prob_pl_list[0])
    posteriors_op = model.posteriors(logits, blank_prior=1)

    # Create a saver for writing training checkpoints
    saver = tf.train.Saver()

    with tf.Session() as sess:
        ckpt = tf.train.get_checkpoint_state(model.save_path)

        # If check point exists
        if ckpt:
            model_path = ckpt.model_checkpoint_path
            if epoch != -1:
                model_path = model_path.split('/')[:-1]
                model_path = '/'.join(model_path) + '/model.ckpt-' + str(epoch)
            saver.restore(sess, model_path)
            print("Model restored: " + model_path)
        else:
            raise ValueError('There are not any checkpoints.')

        plot(session=sess,
             posteriors_op=posteriors_op,
             model=model,
             dataset=test_data,
             label_type=params['label_type'],
             num_stack=params['num_stack'],
             #    save_path=None)
             save_path=mkdir_join(model.save_path, 'ctc_output'))


def plot(session, posteriors_op, model, dataset, label_type,
         num_stack=1, save_path=None, show=False):
    """Visualize label posteriors of CTC model.
    Args:
        session: session of training model
        posteriois_op: operation for computing posteriors
        model: the model to evaluate
        dataset: An instance of a `Dataset` class
        label_type (string): phone39 or phone48 or phone61 or character or
            character_capital_divide
        num_stack (int): the number of frames to stack
        save_path (string, string): path to save ctc outputs
        show (bool, optional): if True, show each figure
    """
    # Clean directory
    if isdir(save_path):
        shutil.rmtree(save_path)
        mkdir(save_path)

    for data, is_new_epoch in dataset:

        # Create feed dictionary for next mini batch
        inputs, _, inputs_seq_len, input_names = data

        feed_dict = {
            model.inputs_pl_list[0]: inputs,
            model.inputs_seq_len_pl_list[0]: inputs_seq_len,
            model.keep_prob_pl_list[0]: 1.0
        }

        # Visualize
        batch_size, max_frame_num = inputs.shape[:2]
        probs = session.run(posteriors_op, feed_dict=feed_dict)
        probs = probs.reshape(-1, max_frame_num, model.num_classes)

        # Visualize
        for i_batch in range(batch_size):
            prob = probs[i_batch][:int(inputs_seq_len[0]), :]

            plt.clf()
            plt.figure(figsize=(10, 4))
            frame_num = int(inputs_seq_len[i_batch])
            times_probs = np.arange(frame_num) * num_stack / 100

            # NOTE: Blank class is set to the last class in TensorFlow
            for i in range(0, prob.shape[-1] - 1, 1):
                plt.plot(times_probs, prob[:, i])
            plt.plot(times_probs, prob[:, -1],
                     ':', label='blank', color='grey')
            plt.xlabel('Time [sec]', fontsize=12)
            plt.ylabel('Posteriors', fontsize=12)
            plt.xlim([0, frame_num * num_stack / 100])
            plt.ylim([0.05, 1.05])
            plt.xticks(list(range(0, int(frame_num * num_stack / 100) + 1, 1)))
            plt.yticks(list(range(0, 2, 1)))
            plt.legend(loc="upper right", fontsize=12)

            if show:
                plt.show()

            # Save as a png file
            if save_path is not None:
                plt.savefig(join(save_path, input_names[0] + '.png'), dvi=500)

        if is_new_epoch:
            break


def main():

    args = parser.parse_args()

    # Load config file
    with open(join(args.model_path, 'config.yml'), "r") as f:
        config = yaml.load(f)
        params = config['param']

    # Except for a blank label
    if params['label_type'] == 'phone61':
        params['num_classes'] = 61
    elif params['label_type'] == 'phone48':
        params['num_classes'] = 48
    elif params['label_type'] == 'phone39':
        params['num_classes'] = 39
    elif params['label_type'] == 'character':
        params['num_classes'] = 28
    elif params['label_type'] == 'character_capital_divide':
        params['num_classes'] = 72
    else:
        raise ValueError

    # Model setting
    model = CTC(encoder_type=params['encoder_type'],
                input_size=params['input_size'],
                splice=params['splice'],
                num_stack=params['num_stack'],
                num_units=params['num_units'],
                num_layers=params['num_layers'],
                num_classes=params['num_classes'],
                lstm_impl=params['lstm_impl'],
                use_peephole=params['use_peephole'],
                parameter_init=params['weight_init'],
                clip_grad_norm=params['clip_grad_norm'],
                clip_activation=params['clip_activation'],
                num_proj=params['num_proj'],
                weight_decay=params['weight_decay'])

    model.save_path = args.model_path
    do_plot(model=model, params=params,
            epoch=args.epoch, eval_batch_size=args.eval_batch_size)


if __name__ == '__main__':
    main()
