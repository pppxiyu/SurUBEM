# Surrogate Modeling for UBEM


## Abstract
Even with a limited number of building prototypes, urban building energy modeling (UBEM)
has to consider the microclimates in the region, as the urban heat island effect and the 
heterogeneous geographical characteristics have an obvious impact on building energy
performances. The number of simulations needed for UBEM is therefore large, and the 
computation time could be days long. Surrogate modeling is a promising way to reduce
the computation time. This repo contains the codes for training surrogate models based
on the annual simulation results in selected microclimates and using the models for UBEM 
with other microclimates.


## Inputs
### Data
Download the dataset from [Google Drive](https://drive.google.com/file/d/1K9-W-cC8ngkglDV2DOMNEwy00WGeFq6w/view?usp=sharing) 
and name it as `data` in the root dir of the project.
Please refer to the work by [Xu et. al.](https://github.com/IMMM-SFA/xu_etal_2022_sdata)
for the explanation of the datasets.

Create a dir `./saved/estimates_tracts` in the root dir of the project.

Running `run_geoVis.py` requires the mapping service of [MapBox](https://www.mapbox.com/).
Please create `mapbox_token.txt` in `./utils`, which contains the mapbox token in one line.
Mapbox account is required to obtain the token. An example of 
mapbox token is `pk.eyJ1IjoicH***********1NXo0M3A5bj*****.f384XN*****`.

### Configuration
Edit the `config.py` to configure the training and estimation.

`features`: a list of string. Supports inputs including 
`'GLW'`, `'PSFC'`, `'Q2'`, `'RH'`, `'SWDOWN'`, `'T2'`, `'WINDD'`, `'WINDS'`, 
and `'Typical' + target_buildingLevel`.

`target_tractLevel`: string. Supports inputs in the `Short Name`
column of the following table.

`target_buildingLevel`: string. Supports inputs in the `Full Name`
column of the following table.

| Short Name | Full Name                                                         |
|------------|-------------------------------------------------------------------|
| emission.surf  | Environment:Site Total Surface Heat Emission to Air \[J](Hourly)  |
| emission.exfiltration | Environment:Site Total Zone Exfiltration Heat Loss \[J](Hourly)   | 
| emission.exhaust | Environment:Site Total Zone Exhaust Air Heat Loss \[J](Hourly)    |
| emission.ref | SimHVAC:Air System Relief Air Total Heat Loss Energy \[J](Hourly) |
| emission.rej | SimHVAC:HVAC System Total Heat Rejection Energy \[J](Hourly)      |
| energy.elec | Electricity:Facility \[J](Hourly)                                 |
| energy.gas | NaturalGas:Facility \[J](Hourly)                                  |

`lag`: list of int. The index of time lags in each sequence, ranging from 1. 
For example, in the case of using 4 time lags to estimate 1 timestamp forward with `'LSTM'`, 
`lag` should be `[1, 2, 3, 4]`. In the case of using 2 timestamps both in the past
and future to estimate the timestamp in the middle with `'biLSTM'`, also use
`[1, 2, 3, 4]`. Please note if `'biLSTM'` is used, the length of `lag` must be 
an even number.

`modelName`: string. Supports `'naive'`, `'LSTM'`, `'biRNN'`, `'linear'`, 
`'mlp'`, and `biRNN_global`.

`tuneTrail`: int. Number of trails in hyperparameter tuning. Only works
for `'LSTM'` and `'biLSTM'`. If set as 1, hyperparameter tuning is disabled.

`maxEpoch`: int. Max epoch count for `'LSTM'` and `'biLSTM'` training.

`saveFolderHead`: string. Recommend name it using the `target_tractLevel`
and the `modelName`. For example, `energyElec_biLSTM` stands for the experiment
using `'biLSTM'` for estimating `'energy.elec'`.

`randomSeed`: int. The random seed used by numpy.random.

`testDataPer`: float, 0-1, only works for the "Option 2" in the `run.py`. 
The percentage of microclimates used for training. 

`dirTargetYear`: `None` or list, only works for the "Option 1" in the `run.py`.
In default, `dirTargetYear` is set as `None`. In this case, the microclimates zones 
in the 2018 is split into training and testing set. However, in real use case, the trained
model will estimate the targets in another year. For this purpose, `dirTargetYear` should be set as a 
list, indicating the dir of input features and ground truth (if any) for test.
The first element is the dir of energy data. The second is for weather data. The third is 
for typical target values. The last one is the tract level ground truth. Example for estimating 2016 whole year:
```
[
'./data/hourly_heat_energy/sim_result_ann_WRF_2016_csv',
'./data/weather input/2016',
'./data/testrun',
'./data/hourly_heat_energy/annual_2016_tract.csv'
]
```

`dayOfWeekJan1`: int. The day of week of the target year of estimation. 1 incicates Monday and 7 indicates
Sunday. 


## Outputs
After configure and run the program, a folder that contains all the outputs for
this run will be generated under `./saved/estimates_tracts`. The output folder
is named with `target_model_notes_experimentTime`. 
For example, `energyElec_biLSTM_GPU-V100_2023-07-21-21-39-29`
is the output folder for estimating electricity with bi-directional LSTM at
21:39:29 07/21 2023 with V100 GPU for training (available targets and model names are introduced below).

`pairListTest.json` and `pairListTrain.json` contains the `prototype-weather` pairs
used for test and training.

The `buildingLevel` folder under the `./saved/estimates_tracts/target_model_experimentTime` contains
the intermediate result. Each `.csv` file contains the hourly estimation of the
target at the building prototype level.

`tractsDF.csv` is the estimation of the target at the census tract level.

`config.py` shows the configuration of this experiment, and other files in the 
`./saved/estimates_tracts/target_model_experimentTime` folder are used for 
the evaluation and visualization of the estimations.


## Requirements
Required packages:
* tensorflow 2
* keras-tuner
* numpy
* pandas
* geopandas
* statesmodel
* scipy
* scikit-learn
* matplotlib
* plotly

Running:
```
python run.py
```

The repo is tested on a NVIDIA V100 GPU, the running using the default config in this
repo can be finished within approximately 1.5 hours.


## Notes

* The typical values of the target is used as a feature. The typical values is obtained
by using simulations for 2018 at LA airport. 2018 starts from Monday. If the year to be
estimated does not start from Monday, there will be a shift between estimation and 
ground truth for some building types. So, the day of week on Jan 1 for target year is a required 
parameter, which will be introduced on the Configuration section. But Please note
the day of week on Jan 1 for training data is hard coded as `1`. Please change it in the 
files under `./model` to revise that if the typical value data is changed.

* 2001 is hard coded in the whole program as the default year. Please update the year
according to the context.

* Training and testing using all prototypes is very time-consuming for debug purposes. `pairListTrain`
and `pairListTest` could be re-written to specify the prototype-microclimate pairs used in training and testing. 
For example:
    ```
    pairListTrain = pairListTrain[0:1]
    pairListTest = pairListTest[0:1]
    ```
  
* Global estimation means using one single model to do the estimation for all prototypes. It is expected to 
generate better accuracy in some cases, because different prototypes share part of the data generation process,
and it works as a simple multitasks learning architecture. Set `modelName = 'biLSTM_global'` will open 
this option. However, the option was not fully developed and the size of training dataset is large.
The total size of training and validation `numpy` array with `float32` type is about 25GB. 

  
## Auxiliary files
`run_preAnalysis.py` conducts preliminary analysis (e.g., visualization, autocorelation plot) 
on the raw data.

`run_resumeEval.py` are kept for debugging and customization purposes. It reloads the saved estimations
for evaluations. 

`run_geoVis.py` is used for drawing maps or other spatial analysis.
