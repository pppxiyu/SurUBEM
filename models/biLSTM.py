import tensorflow as tf
from tensorflow import keras
import keras_tuner as kt

from utils.feature import *
from utils.preprocess import *
from datetime import datetime


class biLSTM(tf.keras.Model):
    def __init__(self, hp_units, name = None, **kwargs):
        super().__init__(**kwargs)
        self.hp_units = hp_units
        self.norm = keras.layers.BatchNormalization()
        self.lstm = keras.layers.LSTM(self.hp_units, return_sequences = True)
        self.bilstm = keras.layers.Bidirectional(self.lstm)   
        self.dense = keras.layers.Dense(1)
        
    def build(self, input_shape):
        self.sequneceLen = input_shape[1]
        self.featureNum = input_shape[2]
        self.midLoc = (self.sequneceLen + 1) // 2
    
    def call(self, x):
        x = self.norm(x)
        x = self.bilstm(x)
        x = x[:, (self.midLoc - 1): self.midLoc, :]
        x_out = self.dense(x)
        return x_out
    
class biLSTM_tuner(kt.HyperModel):
    def build(self, hp):
        hp_units = hp.Int('units', min_value = 256, max_value = 512, step = 128)
        model = biLSTM(hp_units)
        # hp_lr = hp.Float('learningRate', 0.0005, 0.001, step = 0.0005)
        hp_lr = 0.001
        model.compile(optimizer = keras.optimizers.Adam(learning_rate = hp_lr), loss = "mse")
        return model

    def fit(self, hp, model, *args, **kwargs):
        hp_batchSize = hp.Choice('batchSize', values = [128, 512, 1024])
        return model.fit(
            *args,
            batch_size = hp_batchSize,
            **kwargs,
        )
    
def biLSTM_predict(sequenceList_test, tuner):

    model = tuner.get_best_models(num_models = 1)[0]    
    inputShape = sequenceList_test[0][:, :, 1:].shape
    model.build(input_shape = (None, inputShape[1], inputShape[2]))

    predictionList = []
    for testX_0 in sequenceList_test:
        yLoc = int((inputShape[1] + 1) / 2)
        testX = testX_0[:, :, 1:]  # the time lag of energy/heat should not be included
        prediction = model.predict(testX)
        predictionList.append(prediction)
    return predictionList

def train_tract_biRNN(dirs, pairList_train, pairList_test, featureList, target, lag, tuneTrail, maxEpoch, dayOfWeekJan1):
    # USE: use the building-weather pairs in the train pair set to train
    #      do prediction using the new weathers in the test pair set
    # INPUT: all prototype list, pairs for train, pairs for test, featrue names, target name, lag list, ifTune True or False
    # OUTPUT: dict, each value is the prediction for a pair in the test pair set

    dirEnergy = dirs[0]
    dirWeather = dirs[1]
    dirTypical = dirs[2]
    try:
        dirEnergyTarget = dirs[3]
        dirWeatherTarget = dirs[4]
        dirTypicalTarget = dirs[5]
    except:
        dirEnergyTarget = dirEnergy
        dirWeatherTarget = dirWeather
        dirTypicalTarget = dirTypical
        print('Evaluation mode. Train and test data are in same year.')

    # for each of the prototype
    predictionDict = {}
    # for prototypeSelect in getAllPrototype(dirEnergy):
    for prototypeSelect in sorted(list(set([item[0] for item in pairList_test]))):
        ########### train ###########
        print()
        print('---------- Modeling: ', prototypeSelect, ' ----------')

        # get weathers names in train_pairs for the prototype
        protoClimate = [str(item[1]) for item in pairList_train if item[0] == prototypeSelect]
        if len(protoClimate) < 1:
            warnings.warn("Some building type is missing in training dataset.")

        # get weather data in train_pairs for the prototype
        data = getAllData4Prototype(prototypeSelect, protoClimate,
                                    dirEnergy,
                                    dirWeather,
                                    dirTypical,
                                    target,
                                    1, # hard coded, because typical value is obtained in 2018
                                    )
        # build datasets
        trainX, trainY, valX, valY, _, _ = makeDatasets(protoClimate,
                                                        data,
                                                        lag,
                                                        target,
                                                        featureList,
                                                        splitData_biRNN,
                                                        allInTrain = True,
                                                        shuffle = True,
                                                        )
        # train and save model
        tuner = kt.BayesianOptimization(
            biLSTM_tuner(),
            objective = 'val_loss',
            max_trials = tuneTrail,
            overwrite = True,
            directory = './tuner',
            project_name = 'biLSTM ' + str(datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
        )
        tuner.search(trainX, trainY,
                     epochs=maxEpoch,
                     callbacks=[tf.keras.callbacks.EarlyStopping('val_loss', patience=3, min_delta=0, ), ],
                     validation_data=(valX, valY),
                     )
        model = tuner.get_best_models(num_models=1)[0]
        model.build(input_shape=(None, trainX.shape[1], trainX.shape[2]))

        ########### predict ###########

        # predict the test building-weather pairs whose prototype is in this loop
        protoClimate_predict = [item[1] for item in pairList_test if item[0] == prototypeSelect]
        if len(protoClimate_predict) == 0:
            print('A model trained is not used in test.')

        for weatherSelect in protoClimate_predict:
            print('    ---------- Building-Weather pair under estimation: ', prototypeSelect, '____', weatherSelect,
                  ' ----------')

            # get data of each weather
            weatherSelect = str(weatherSelect)
            data_energy = importRawData(
                dirEnergyTarget + '/' + prototypeSelect + '____' + weatherSelect + '.csv',
                col = target
                )
            data_weatherSelect = importWeatherData(dirWeatherTarget, weatherSelect)
            data_typical = importTypical(dirTypicalTarget, prototypeSelect,
                                         target, dayOfWeekJan1)
            data = pd.concat([data_energy, data_weatherSelect, data_typical], axis=1)
            dataShort = data[[target] + featureList]
            sequences = sequencesGeneration(dataShort, lag, featureList, target)

            # estimation
            sequences_x = sequences[:, :, 1:]
            prediction = model.predict(sequences_x)

            # record prediction
            lagShift = (len(lag) + 1) // 2
            predictionDF = pd.DataFrame(prediction[:, 0], columns = ['estimate'])
            predictionDF['true'] = sequences[:, lagShift: (lagShift + 1), 0]
            predictionDF['DateTime'] = pd.date_range(start='2001-01-01 00:00:00', end='2001-12-31 23:00:00',
                                                     freq='H').to_series().iloc[lagShift: -lagShift].to_list()
            predictionDict[prototypeSelect + '____' + weatherSelect] = predictionDF

    return predictionDict


if __name__ == '__main__':
    pass