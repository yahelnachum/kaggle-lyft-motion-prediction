#>
import gc
import os

import numpy as np

#>
import zarr

import l5kit
from l5kit.data import ChunkedDataset, LocalDataManager

print("l5kit version:", l5kit.__version__)

#>
os.environ["L5KIT_DATA_FOLDER"] = "/kaggle/input/lyft-motion-prediction-autonomous-vehicles"

#>
import time
from datetime import datetime

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
dm = LocalDataManager()
dataset_path = dm.require('scenes/test.zarr')
zarr_dataset = ChunkedDataset(dataset_path)
zarr_dataset.open()
print(zarr_dataset)

#>
print(zarr_dataset.agents)
print(zarr_dataset.agents.shape)
n = zarr_dataset.agents.shape

#>
test_mask = np.load('../input/lyft-motion-prediction-autonomous-vehicles/scenes/mask.npz')
for k in test_mask.files:
    print("key:",k)
test_mask = test_mask["arr_0"]
print("test_mask", test_mask)
print("test_mask.shape", test_mask.shape)
print("test_mask[0]", test_mask[0])

#>
def getAgentsChunked(dataset, subsetPercent=1, chunkSize=10, mask_copy=[]):

    datasetLength = round(len(dataset) * subsetPercent)
    print("datasetLength", datasetLength)
    print("chunkSize", chunkSize)
    agents = {}
    pb = ProgressBar(datasetLength)
    pb.start()
    for i in range(0, datasetLength, chunkSize):

        agentsSubset = dataset[i:i+chunkSize]
        for j in range(0,len(agentsSubset)):
            pb.check(i+j)
            if len(mask_copy) > 0 and (j + i < len(mask_copy)) and not(mask_copy[i+j]):
                continue
            
            agent = agentsSubset[j]
            
            centroid = agent[0]
            yaw = agent[2]
            velocity = agent[3]
            track_id = agent[4]

            if track_id not in agents:
                agents[track_id] = []
                
            data = []
            data.append(centroid[0])
            data.append(centroid[1])
            data.append(yaw)
            data.append(velocity[0])
            data.append(velocity[1])
            
            agents[track_id].append(data)
            

    return agents

#>
subsetPercent = 1*10**-2
subsetLength = round(len(test_mask) * subsetPercent)
print("subsetLength", subsetLength)
count = 0
pb = ProgressBar(subsetLength)
pb.start()
chunkSize = 1000
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
        pb.check(i+j)
pb.end()
print("count", count)

#>
print(subsetPercent)
agents = getAgentsChunked(zarr_dataset.agents, subsetPercent, 1000, mask_copy)

#>
print(len(agents))

lengthOfAgents = []
pb = ProgressBar(len(agents))
count = 0
pb.start()
for key in agents:
    agent = agents[key]
    lengthOfAgents.append(len(agent))
    count += 1
    pb.check(count)
pb.end()

print(len(lengthOfAgents))

#>
mean = np.mean(lengthOfAgents)
std = np.std(lengthOfAgents)
min_ = np.min(lengthOfAgents)
max_ = np.max(lengthOfAgents)
median = np.median(lengthOfAgents)

print("mean",mean)
print("std",std)
print("min_",min_)
print("max_",max_)
print("median",median)

#>
framesIntervalIndex = 0
print("frames interval", zarr_dataset.scenes[0][framesIntervalIndex])
frameStart = zarr_dataset.scenes[0][framesIntervalIndex][0]
frameEnd = zarr_dataset.scenes[0][framesIntervalIndex][1]

agentsIntervalIndex = 1
print("agents interval", zarr_dataset.frames[0][agentsIntervalIndex])

#>
print(frameStart, frameEnd)

#>
agents = {}
for i in range(frameStart, frameEnd):
    frame = zarr_dataset.frames[i]
    
    agentsInterval = frame[agentsIntervalIndex]
    
    agentsStart = agentsInterval[0]
    agentsEnd = agentsInterval[1]
    
    for j in range(agentsStart, agentsEnd):
        
        if not (mask_copy[j]):
            continue
        
        print(i, agentsStart, agentsEnd)
        agent = zarr_dataset.agents[j]
        
        centroid = agent[0]
        yaw = agent[2]
        velocity = agent[3]
        track_id = agent[4]

        if track_id not in agents:
            agents[track_id] = []

        data = []
        data.append(centroid[0])
        data.append(centroid[1])
        data.append(yaw)
        data.append(velocity[0])
        data.append(velocity[1])

        agents[track_id].append(data)

#>
len(agents[2])

#>
