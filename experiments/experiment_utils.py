""" Utilities used in the rest of the library """

import os
import pickle
import numpy as np
import math

from seldonian.RL.RL_runner import create_agent, run_trial_given_agent_and_env
from seldonian.utils.stats_utils import weighted_sum_gamma
from seldonian.dataset import SupervisedDataSet
from seldonian.utils.io_utils import load_pickle

def generate_resampled_datasets(dataset, n_trials, save_dir):
    """Utility function for supervised learning to generate the
    resampled datasets to use in each trial. Resamples (with replacement)
    features, labels and sensitive attributes to create n_trials versions of these
    of the same shape as the inputs

    :param dataset: The original dataset from which to resample
    :type dataset: pandas DataFrame

    :param n_trials: The number of trials, i.e. the number of
            resampled datasets to make
    :type n_trials: int

    :param save_dir: The parent directory in which to save the
            resampled datasets
    :type save_dir: str

    :param file_format: The format of the saved datasets, options are
            "csv" and "pkl"
    :type file_format: str

    """
    save_subdir = os.path.join(save_dir, "resampled_dataframes")
    os.makedirs(save_subdir, exist_ok=True)
    num_datapoints = dataset.num_datapoints

    for trial_i in range(n_trials):
        savename = os.path.join(save_subdir, f"trial_{trial_i}.pkl")

        if not os.path.exists(savename):
            ix_resamp = np.random.choice(
                range(num_datapoints), num_datapoints, replace=True
            )
            # features can be list of arrays or a single array
            if type(dataset.features) == list:
                resamp_features = [x[ix_resamp] for x in flist]
            else:
                resamp_features = dataset.features[ix_resamp]

            # labels and sensitive attributes must be arrays
            resamp_labels = dataset.labels[ix_resamp]
            if isinstance(dataset.sensitive_attrs, np.ndarray):
                resamp_sensitive_attrs = dataset.sensitive_attrs[ix_resamp]
            else:
                resamp_sensitive_attrs = []

            resampled_dataset = SupervisedDataSet(
                features=resamp_features,
                labels=resamp_labels,
                sensitive_attrs=resamp_sensitive_attrs,
                num_datapoints=num_datapoints,
                meta_information=dataset.meta_information,
            )

            with open(savename, "wb") as outfile:
                pickle.dump(resampled_dataset, outfile)
            print(f"Saved {savename}")

def load_resampled_dataset(results_dir,trial_i,data_frac,verbose=False):
    """Utility function for supervised learning to generate the
    resampled datasets to use in each trial. Resamples (with replacement)
    features, labels and sensitive attributes to create n_trials versions of these
    of the same shape as the inputs

    :param results_dir: The directory in which results are saved for this trial
    :type results_dir: str

    :param trial_i: Trial index
    :type trial_i: int

    :param data_frac: data fraction
    :type data_frac: float

    :param verbose: boolean verbosity flag
    """
    resampled_filename = os.path.join(
                results_dir, "resampled_dataframes", f"trial_{trial_i}.pkl"
    )
    resampled_dataset = load_pickle(resampled_filename)
    num_datapoints_tot = resampled_dataset.num_datapoints
    n_points = int(round(data_frac * num_datapoints_tot))

    if verbose:
        print(
            f"Using resampled dataset {resampled_filename} "
            f"with {num_datapoints_tot} datapoints"
        )
    if n_points < 1:
        raise ValueError(
            f"This data_frac={data_frac} "
            f"results in {n_points} data points. "
            "Must have at least 1 data point to run a trial."
        )
    return resampled_dataset,n_points

def generate_episodes_and_calc_J(**kwargs):
    """Calculate the expected discounted return
    by generating episodes

    :return: episodes, J, where episodes is the list
            of generated ground truth episodes and J is
            the expected discounted return
    :rtype: (List(Episode),float)
    """
    # Get trained model weights from running the Seldonian algo
    model = kwargs["model"]
    new_params = model.policy.get_params()

    # create env and agent
    hyperparameter_and_setting_dict = kwargs["hyperparameter_and_setting_dict"]
    agent = create_agent(hyperparameter_and_setting_dict)
    env = hyperparameter_and_setting_dict["env"]

    # set agent's weights to the trained model weights
    agent.set_new_params(new_params)

    # generate episodes
    num_episodes = kwargs["n_episodes_for_eval"]
    episodes = run_trial_given_agent_and_env(
        agent=agent, env=env, num_episodes=num_episodes
    )

    # Calculate J, the discounted sum of rewards
    returns = np.array([weighted_sum_gamma(ep.rewards, env.gamma) for ep in episodes])
    J = np.mean(returns)
    return episodes, J

def batch_predictions(model, solution, X_test, **kwargs):
    batch_size = kwargs["eval_batch_size"]
    if type(X_test) == list:
        N_eval = len(X_test[0])
    else:
        N_eval = len(X_test)
    if "N_output_classes" in kwargs:
        N_output_classes = kwargs["N_output_classes"]
        y_pred = np.zeros((N_eval, N_output_classes))
    else:
        y_pred = np.zeros(N_eval)
    num_batches = math.ceil(N_eval / batch_size)
    batch_start = 0
    for i in range(num_batches):
        batch_end = batch_start + batch_size

        if type(X_test) == list:
            X_test_batch = [x[batch_start:batch_end] for x in X_test]
        else:
            X_test_batch = X_test[batch_start:batch_end]
        y_pred[batch_start:batch_end] = model.predict(solution, X_test_batch)
        batch_start = batch_end
    return y_pred

def make_batch_epoch_dict_fixedniter(niter,data_fracs,N_max,batch_size):
    """
    Convenience function for figuring out the number of epochs necessary
    to ensure that at each data fraction, the total 
    number of iterations (and batch size) will be fixed. 

    :param niter: The total number of iterations you want run at every data_frac
    :type niter: int
    :param data_fracs: 1-D array of data fractions
    :type data_fracs: np.ndarray 
    :param N_max: The maximum number of data points in the optimization process
    :type N_max: int
    :param batch_size: The fixed batch size 
    :type batch_size: int
    :return batch_epoch_dict: A dictionary where keys are data fractions 
        and values are [batch_size,num_epochs]
    """
    data_sizes=data_fracs*N_max # number of points used in candidate selection in each data frac
    n_batches=data_sizes/batch_size # number of batches in each data frac
    n_batches=np.array([math.ceil(x) for x in n_batches])
    n_epochs_arr=niter/n_batches # number of epochs needed to get to niter iterations in each data frac
    n_epochs_arr = np.array([math.ceil(x) for x in n_epochs_arr])
    batch_epoch_dict = {
        data_fracs[ii]:[batch_size,n_epochs_arr[ii]] for ii in range(len(data_fracs))}
    return batch_epoch_dict

def make_batch_epoch_dict_min_sample_repeat(
    niter_min,
    data_fracs,
    N_max,
    batch_size,
    num_repeats):
    """
    Convenience function for figuring out the number of epochs necessary
    to ensure that the number of iterations for each data frac is:
    max(niter_min,# of iterations s.t. each sample is seen num_repeat times)

    :param niter_min: The minimum total number of iterations you want run at every data_frac
    :type niter_min: int
    :param data_fracs: 1-D array of data fractions
    :type data_fracs: np.ndarray 
    :param N_max: The maximum number of data points in the optimization process
    :type N_max: int
    :param batch_size: The fixed batch size
    :type batch_size: int
    :param num_repeats: The minimum number of times each sample must be seen in the optimization process
    :type num_repeats: int
    :return batch_epoch_dict: A dictionary where keys are data fractions 
        and values are [batch_size,num_epochs]
    """
    batch_epoch_dict = {}
    n_epochs_arr = np.zeros_like(data_fracs)
    for data_frac in data_fracs:
        niter2 = num_repeats*N_max*data_frac/batch_size
        if niter2 > niter_min:
            num_epochs = num_repeats
        else:
            n_batches = max(1,N_max*data_frac/batch_size)
            num_epochs = math.ceil(niter_min/n_batches)
        batch_epoch_dict[data_frac] = [batch_size,num_epochs]
    
    return batch_epoch_dict

def has_failed(g):
    """ Condition for whether a value of g is unsafe. This is used
    to determine the failure rate in the right-most plot of the experiments plots.

    :param g: The value of the behavioral constraint evaluated using a model and data 
    :type g: float

    :return: True if g is unsafe, False if g is safe
    """
    return g>0 or np.isnan(g)

