#>
import gc
import os
from pathlib import Path
import random
import sys

from tqdm.notebook import tqdm
import numpy as np
import pandas as pd
import scipy as sp


import matplotlib.pyplot as plt
import seaborn as sns

from IPython.core.display import display, HTML

# --- plotly ---
from plotly import tools, subplots
import plotly.offline as py
py.init_notebook_mode(connected=True)
import plotly.graph_objs as go
import plotly.express as px
import plotly.figure_factory as ff
import plotly.io as pio
pio.templates.default = "plotly_dark"

# --- models ---
from sklearn import preprocessing
from sklearn.model_selection import KFold
import lightgbm as lgb
import xgboost as xgb
import catboost as cb

# --- setup ---
pd.set_option('max_columns', 50)

#>
import zarr

import l5kit
from l5kit.data import ChunkedDataset, LocalDataManager
from l5kit.dataset import EgoDataset, AgentDataset

from l5kit.rasterization import build_rasterizer
from l5kit.configs import load_config_data
from l5kit.visualization import draw_trajectory, TARGET_POINTS_COLOR
from l5kit.geometry import transform_points
from tqdm import tqdm
from collections import Counter
from l5kit.data import PERCEPTION_LABELS
from prettytable import PrettyTable

from matplotlib import animation, rc
from IPython.display import HTML

rc('animation', html='jshtml')
print("l5kit version:", l5kit.__version__)

#>
# Importing the libraries
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('fivethirtyeight')
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import Dense, LSTM, Dropout, GRU, Bidirectional
from keras.optimizers import SGD
import math
from sklearn.metrics import mean_squared_error

#>
import time
from datetime import datetime

#>
os.environ["L5KIT_DATA_FOLDER"] = "/kaggle/input/lyft-motion-prediction-autonomous-vehicles"

#>
dm = LocalDataManager()
dataset_path = dm.require('scenes/sample.zarr')
zarr_dataset = ChunkedDataset(dataset_path)
zarr_dataset.open()
print(zarr_dataset)

#>
print(zarr_dataset.agents)
print(zarr_dataset.agents.shape)
n = zarr_dataset.agents.shape

#>
# helper to convert a timedelta to a string (dropping milliseconds)
def deltaToString(delta):
    timeObj = time.gmtime(delta.total_seconds())
    return time.strftime('%H:%M:%S', timeObj)

class ProgressBar:
    
    # constructor
    #   maxIterations: maximum number of iterations
    def __init__(self, maxIterations):
        self.maxIterations = maxIterations
        self.granularity = 100 # 1 whole percent
    
    # start the timer
    def start(self):
        self.start = datetime.now()
    
    # check the progress of the current iteration
    #   # currentIteration: the current iteration we are on
    def check(self, currentIteration, chunked=False):
        if currentIteration % round(self.maxIterations / self.granularity) == 0 or chunked:
            
            percentage = round(currentIteration / (self.maxIterations - self.maxIterations / self.granularity) * 100)
            
            current = datetime.now()
            
            # time calculations
            timeElapsed = (current - self.start)
            timePerStep = timeElapsed / (currentIteration + 1)
            totalEstimatedTime = timePerStep * self.maxIterations
            timeRemaining = totalEstimatedTime - timeElapsed
            
            # string formatting
            percentageStr = "{:>3}%  ".format(percentage)
            remainingStr = "Remaining: {}  ".format(deltaToString(timeRemaining))
            elapsedStr = "Elapsed: {}  ".format(deltaToString(timeElapsed))
            totalStr = "Total: {}\r".format(deltaToString(totalEstimatedTime))
            
            print(percentageStr + remainingStr + elapsedStr + totalStr, end="")

    def end(self):
        print()

#>
def getAgentsChunked(dataset, subsetPercent=1, chunks=10, mask_copy=[]):

    datasetLength = round(len(dataset) * subsetPercent)
    chunkSize = round(datasetLength / chunks)
    
    pb = ProgressBar(datasetLength)
    pb.start()

    agents = []
    for i in range(0, datasetLength, chunkSize):

        agentsSubset = dataset[i:i+chunkSize]
        for j in range(0,len(agentsSubset)):
            if len(mask_copy) > 0 and (j + i < len(mask_copy)) and not(mask_copy[i+j]):
                continue
            
            agent = agentsSubset[j]
            track_id = agent[4]

            while track_id >= len(agents):
                agents.append([])

            data = []
            centroid = agent[0]
            yaw = agent[2]
            velocity = agent[3]
            data.append(centroid[0])
            data.append(centroid[1])
            data.append(yaw)
            data.append(velocity[0])
            data.append(velocity[1])
            
            agents[int(track_id)-1].append(data)
            
        pb.check(i, True)

    return agents

#>
print(zarr_dataset.agents, "\n")
print(type(zarr_dataset.agents[0][0][0]))
print(type(zarr_dataset.agents[0][0]))
print(type(zarr_dataset.agents[0]))
print(type(zarr_dataset.agents))
agents = []
print(type(agents))

#>
subsetPercent = 1*10**-1
print(subsetPercent)
agents = getAgentsChunked(zarr_dataset.agents, subsetPercent, 100)

#>
def plotAgents(agents):
    r = lambda: random.randint(0,255)
    pb = ProgressBar(len(agents))
    pb.start()
    for i in range(0, len(agents)):
        agent = agents[i]
        centroid_x = []
        centroid_y = []
        for centroid in agent:
            centroid_x.append(centroid[0])
            centroid_y.append(centroid[1])
        plt.plot(centroid_x, centroid_y, 'o', color='#%02X%02X%02X' % (r(),r(),r()))
        pb.check(i)

#>
plotAgents(agents)

#>
def normalizeAgents(agents):
    dataForNormalization = []
    pb = ProgressBar(len(agents))
    pb.start()
    for i in range(0, len(agents)):
        agent = agents[i]
        pb.check(i)
        for data in agent:
            for i in range(0, len(data)):
                feature = data[i]
                if i >= len(dataForNormalization):
                    dataForNormalization.append([])
                dataForNormalization[i].append(feature)
        
    
    first = True
    normalizedAgents = []
    pb = ProgressBar(len(dataForNormalization) * len(agents))
    counter = 0
    pb.start()
    for i in range(0, len(dataForNormalization)):
        pb.end()
        data = dataForNormalization[i]
        min_ = np.min(data)
        max_ = np.max(data)
        print("max[{}]".format(i),max_)
        print("min[{}]".format(i),min_,"\n")
        
        for j in range(0, len(agents)):
            counter = counter + 1
            pb.check(counter)
            if j >= len(normalizedAgents):
                normalizedAgents.append([])
                
            agent = agents[j]
            normalizedAgent = normalizedAgents[j]
            
            for k in range(0, len(agent)):
                if k >= len(normalizedAgent):
                    normalizedAgent.append([])
                data = agent[k]
                normalizedData = normalizedAgent[k]
                
                feature = data[i]
                normalizedFeature = (feature - min_) / (max_ - min_)
                if i == 0 and first:
                    print(feature)
                    print(normalizedFeature)
                    first = False
                
                if i >= len(normalizedData):
                    normalizedData.append(0)
                normalizedData[i] = normalizedFeature
    return normalizedAgents

#>
import copy

#>
normalizedAgents = normalizeAgents(agents)

#>
print(len(agents))
print(len(normalizedAgents),"\n")

print(agents[0][0][0])
print(normalizedAgents[0][0][0],"\n")

#>
def printAgentsInfo(agents, limit):
    print("len(agents)", len(agents), "\n")

    agentCentroidLengths = []
    agentsOverLimit = []
    for agent in agents:
        agentCentroidLengths.append(len(agent))
        if len(agent) > limit:
            agentsOverLimit.append(agent)

    print("len(agentCentroidLengths)",len(agentCentroidLengths), "\n")

    print("max",np.max(agentCentroidLengths))
    print("min",np.min(agentCentroidLengths))
    print("mean",np.mean(agentCentroidLengths))
    print("std",np.std(agentCentroidLengths), "\n")

    print("agents with {}+ history".format(limit),len(agentsOverLimit))
    return agentsOverLimit

#>
limit = 10
agentsOverLimit = printAgentsInfo(normalizedAgents, limit)

#>
def getTrainingSets(agents, limit):
    allTrainingSets = []
    totalNumberOfTrainingSets = 0
    
    pb = ProgressBar(len(agentsOverLimit))
    pb.start()
    for i in range(0, len(agentsOverLimit)):
        agent = agentsOverLimit[i]
        agentTrainingSets = []
        for i in range(limit, len(agent)-1):
            agentTrainingSet = []

            start = i - limit
            end = i
            output = i + 1

            agentTrainingSet.append(agent[start:end])
            agentTrainingSet.append(agent[output])
            agentTrainingSets.append(agentTrainingSet)

            totalNumberOfTrainingSets = totalNumberOfTrainingSets + 1

        allTrainingSets.append(agentTrainingSets)
        pb.check(i)
    pb.end()
    
    print("len(allTrainingSets)", len(allTrainingSets))
    print("len(allTrainingSets[0])",len(allTrainingSets[0]), "\n")

    print("len(agentsOverLimit)",len(agentsOverLimit))
    print("len(agentsOverLimit[0]) - limit - 1",len(agentsOverLimit[0]) - limit - 1, "\n")

    print("totalNumberOfTrainingSets",totalNumberOfTrainingSets)
    return allTrainingSets, totalNumberOfTrainingSets

#>
allTrainingSets, totalNumberOfTrainingSets = getTrainingSets(agentsOverLimit, limit)

#>
print(len(allTrainingSets))
print(len(allTrainingSets[0]))
print(len(allTrainingSets[0][0]))
print(len(allTrainingSets[0][0][0]))
print(len(allTrainingSets[0][0][0][0]))

#>
def flattenTrainingSets(allTrainingSets, totalNumberOfTrainingSets):
    allTrainingSetsFlattened_X = np.empty((totalNumberOfTrainingSets, limit, len(allTrainingSets[0][0][0][0])))
    allTrainingSetsFlattened_Y = np.empty((totalNumberOfTrainingSets, len(allTrainingSets[0][0][0][0])))
    count = 0
    for allTrainingSet in allTrainingSets:
        for trainingSet in allTrainingSet:
            allTrainingSetsFlattened_X[count] = np.array(trainingSet[0])
            allTrainingSetsFlattened_Y[count] = trainingSet[1]
            count = count + 1
    print("len(allTrainingSetsFlattened_X)", len(allTrainingSetsFlattened_X))
    return allTrainingSetsFlattened_X, allTrainingSetsFlattened_Y

#>
allTrainingSetsFlattened_X, allTrainingSetsFlattened_Y = flattenTrainingSets(allTrainingSets, totalNumberOfTrainingSets)

#>
length = len(allTrainingSetsFlattened_X)
depth = len(allTrainingSetsFlattened_X[0])
channels = len(allTrainingSetsFlattened_X[0][0])

print("length", length)
print("depth", depth)
print("channels",channels)
print("length*depth*channels",length*depth*channels)

allTrainingSetsFlattened_Input = allTrainingSetsFlattened_X
allTrainingSetsFlattened_Output = allTrainingSetsFlattened_Y

print(allTrainingSetsFlattened_Input.shape[1])
print(allTrainingSetsFlattened_Input.shape[2])

#>
# The LSTM architecture
regressor = Sequential()
# First LSTM layer with Dropout regularisation
regressor.add(LSTM(units=50, return_sequences=True, input_shape=(allTrainingSetsFlattened_Input.shape[1],allTrainingSetsFlattened_Input.shape[2])))
regressor.add(Dropout(0.2))
# Second LSTM layer
regressor.add(LSTM(units=50, return_sequences=True))
regressor.add(Dropout(0.2))
# Third LSTM layer
regressor.add(LSTM(units=50, return_sequences=True))
regressor.add(Dropout(0.2))
# Fourth LSTM layer
regressor.add(LSTM(units=50))
regressor.add(Dropout(0.2))
# The output layer
regressor.add(Dense(units=allTrainingSetsFlattened_Input.shape[2]))

# Compiling the RNN
regressor.compile(optimizer='rmsprop',loss='mean_squared_error')

#>
from tensorflow import keras

#>
# Fitting to the training set

class CustomCallback(keras.callbacks.Callback):
    
    def __init__(self):
        self.epoch = 0
        
    def on_epoch_end(self, epoch, logs=None):
        keys = list(logs.keys())
        print("Epoch: {}             loss: {}\n".format(self.epoch, logs['loss']), end="")
        self.epoch = epoch

    def on_train_batch_end(self, batch, logs=None):
        keys = list(logs.keys())
        if batch % 100 == 0:
            print("Epoch: {} batchs: {}% loss: {}\r".format(self.epoch, round(batch / self.params['steps'] * 100), logs['loss']), end="")

regressor.fit(allTrainingSetsFlattened_Input,allTrainingSetsFlattened_Output,epochs=2,batch_size=128,verbose=0,callbacks=[CustomCallback()])

#>
dataset_path_test = dm.require('scenes/test.zarr')
zarr_dataset_test = ChunkedDataset(dataset_path_test)
zarr_dataset_test.open()
print(zarr_dataset_test)

#>
test_mask = np.load('../input/lyft-motion-prediction-autonomous-vehicles/scenes/mask.npz')["arr_0"]
print(test_mask)
print(test_mask.shape)
print(test_mask[0])

#>
subsetPercent = 1 * 10**-1
subsetLength = round(len(test_mask) * subsetPercent)
count = 0
pb = ProgressBar(subsetLength)
pb.start()
chunkSize = 10
mask_copy = []
mask_indexes = []
for i in range(0, subsetLength, chunkSize):
    chunkedTestMask = test_mask[i: i + chunkSize]
    for j in range(0, len(chunkedTestMask)):
        mask = chunkedTestMask[j]
        mask_copy.append(mask)
        if mask:
            mask_indexes.append(i + j)
            count = count + 1
    pb.check(i)
pb.end()
print(count)

#>
prev = mask_indexes[0]
diffs = []
for i in range(1, len(mask_indexes)):
    curr = mask_indexes[i]
    diff = curr - prev
    diffs.append(diff)
    prev = curr
print(diffs[0:10])

#>
print("max",np.max(diffs))
print("min",np.min(diffs))
print("median",np.median(diffs))
print("mean",np.mean(diffs))
print("std",np.std(diffs), "\n")

#>
print(len(zarr_dataset_test.agents))

#>
subsetPercent = 1*10**-1
print(subsetPercent)
agentsTest = getAgentsChunked(zarr_dataset_test.agents, subsetPercent, 1000, mask_copy)

#>
plotAgents(agents)

#>
normalizedAgentsTest = normalizeAgents(agentsTest)

#>
agentsTestOverLimit = printAgentsInfo(normalizedAgentsTest, limit)

#>
allTestingSets, totalNumberOfTestingSets = getTrainingSets(agentsTestOverLimit, limit)

#>
allTestingSetsFlattened_X, allTestingSetsFlattened_Y = flattenTrainingSets(allTestingSets, totalNumberOfTestingSets)

#>
allTestingSetsFlattened_Input = allTestingSetsFlattened_X
allTestingSetsFlattened_Output = allTestingSetsFlattened_Y

#>
print(allTestingSetsFlattened_Input.shape)

#>
max = len(allTestingSetsFlattened_Input)
print(max)
chunkSize = 100
pb = ProgressBar(max)
pb.start()
predictedTestAgentCentroid = np.empty((1,5))
for i in range(0, max-chunkSize, chunkSize):#len(zarr_dataset.agents)):
    newPredictions = regressor.predict(allTestingSetsFlattened_Input[i:i+chunkSize])
    print(newPredictions.shape)
    predictedTestAgentCentroid = np.concatenate((predictedTestAgentCentroid, newPredictions))
    pb.check(i, True)

#>
print(predictedTestAgentCentroid.shape)

#>
print(predictedTestAgentCentroid.shape)
predictedTestAgentCentroid = predictedTestAgentCentroid[1:len(predictedTestAgentCentroid)]
print(predictedTestAgentCentroid.shape)

#>
print(len(predictedTestAgentCentroid))

#>
randomSamples = 10
for i in range(0, len(predictedTestAgentCentroid), round(len(predictedTestAgentCentroid) / randomSamples)):
    testSet = allTestingSetsFlattened_Input[i]
    lastTestSet = testSet[len(testSet[0]) - 1][0]
    firstPrediction = predictedTestAgentCentroid[i][0]
    print(lastTestSet)
    print(firstPrediction,"\n")

#>
csv_path = "submission.csv"
testCSVOutput = np.empty((5,50,2))
print(testCSVOutput.shape)

#>
import os

#>
if os.path.exists(csv_path):
    os.remove(csv_path)

#>
dummyData = np.empty((10,50,2))

#>
file = open(csv_path, 'w')

def printCoord(row, axis, confidence, timestep):
    return row + "coord_" + axis + str(confidence) + str(timestep) + ","
    
# timestamp track_id conf_0 conf_1 conf_2	coord_x00 coord_y249
row = ""
row = row + "timestamp" + ","
row = row + "track_id" + ","
for i in range(0,3):
    row = row + "conf_" + str(i) + ","
for confidence in range(0,3):
    for timestep in range(0,50):
        row = printCoord(row, "x", confidence, timestep)
        row = printCoord(row, "y", confidence, timestep)
row = row + "\n"
print(row)
file.write(row)

#>
for i in range(0, len(dummyData)):
    idRow = dummyData[i]
    row = ""
    row = str(i)
    for future in idRow:
        for pos in future:
            row = row + str(pos) + ","
    row = row + "\n"
    print(row)
    file.write(row)

#>
file.close()

#>

