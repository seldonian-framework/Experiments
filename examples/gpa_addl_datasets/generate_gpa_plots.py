import os
import numpy as np 

from experiments.generate_plots import SupervisedPlotGenerator
from experiments.baselines.logistic_regression import BinaryLogisticRegressionBaseline
from experiments.baselines.random_classifiers import (
    UniformRandomClassifierBaseline,WeightedRandomClassifierBaseline)
from experiments.baselines.random_forest import RandomForestClassifierBaseline
from seldonian.utils.io_utils import load_pickle
from sklearn.metrics import log_loss,accuracy_score

def perf_eval_fn(y_pred,y,**kwargs):
    # Deterministic accuracy. Should really be using probabilistic accuracy, 
    # but use deterministic to match Thomas et al. (2019)
    return accuracy_score(y,y_pred > 0.5)

def initial_solution_fn(m,X,Y):
    return m.fit(X,Y)

def main():
    # Parameter setup
    run_experiments = False
    make_plots = False
    save_plot = False
    include_legend = True

    model_label_dict = {
        'qsa':'Seldonian model (with additional datasets)',
        }

    constraint_name = 'demographic_parity'
    performance_metric = 'accuracy'
    n_trials = 20
    data_fracs = np.logspace(-4,0,15)
    n_workers = 8
    results_dir = f'results/test_demographic_parity'
    plot_savename = os.path.join(results_dir,f'gpa_{constraint_name}_{performance_metric}.png')

    verbose=True

    # Load spec
    specfile = f'specfiles/demographic_parity_addl_datasets.pkl'
    spec = load_pickle(specfile)
    print(spec.dataset.num_datapoints)
    os.makedirs(results_dir,exist_ok=True)

    # Use entire original primary dataset as ground truth for test set
    dataset = spec.dataset
    test_features = dataset.features
    test_labels = dataset.labels

    # Setup performance evaluation function and kwargs 
    perf_eval_kwargs = {
        'X':test_features,
        'y':test_labels,
        'performance_metric':performance_metric
        }

    # Use original additional_datasets as ground truth (for evaluating safety)
    constraint_eval_kwargs = {}
    constraint_eval_kwargs["additional_datasets"] = spec.additional_datasets

    plot_generator = SupervisedPlotGenerator(
        spec=spec,
        n_trials=n_trials,
        data_fracs=data_fracs,
        n_workers=n_workers,
        datagen_method='resample',
        perf_eval_fn=perf_eval_fn,
        constraint_eval_fns=[],
        constraint_eval_kwargs=constraint_eval_kwargs,
        results_dir=results_dir,
        perf_eval_kwargs=perf_eval_kwargs,
        )

    if run_experiments:

        # Seldonian experiment
        plot_generator.run_seldonian_experiment(verbose=verbose)


    if make_plots:
        plot_generator.make_plots(fontsize=12,legend_fontsize=8,
            performance_label=performance_metric,
            include_legend=include_legend,
            model_label_dict=model_label_dict,
            save_format="png",
            savename=plot_savename if save_plot else None)


if __name__ == "__main__":
    main()