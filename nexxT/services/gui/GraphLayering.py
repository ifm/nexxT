# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from collections import deque

class GraphRep:
    def __init__(self, baseGraphScene = None):
        self.id2name = {}
        self.name2id = {}
        self.dgForward = {} # mapping id's to successor sets
        self.dgBackward = {} # mapping id's to predessor sets
        self.cycleEdges = set()
        self.longEdges = set()
        if baseGraphScene is not None:
            for n in baseGraphScene.nodes.keys():
                self.addNode(n)
            for c in baseGraphScene.connections:
                self.addEdge(c.portFrom.nodeItem.name, c.portTo.nodeItem.name)

    def addNode(self, n):
        i = len(self.name2id)
        self.id2name[i] = n
        self.name2id[n] = i
        self.dgForward[i] = set()
        self.dgBackward[i] = set()
        self.n = i+1
        self.vn = self.n

    def addEdge(self, n1, n2):
        fromId = self.name2id[n1]
        toId = self.name2id[n2]
        if toId in self.dgForward[fromId]:
            return
        self.dgForward[fromId].add(toId)
        self.dgBackward[toId].add(fromId)

    def dump(self, title = None):
        if title is not None: print(title)
        for n1 in self.dgForward:
            print(n1, end=": ")
            for n2 in self.dgForward[n1]:
                if (n1,n2) not in self.cycleEdges:
                    print(n2, end=",")
            print()
        print()

    def topological_sort(self):
        self.dump("original:")
        permanent = [False] * self.n
        temporary = [False] * self.n
        self.cycleEdges = set()

        result = deque()
        def visit(cId, pId):
            if permanent[cId]:
                return
            if temporary[cId]:
                # not a DAG, but we just continue as if the edge
                # does not exist
                self.cycleEdges.add((pId, cId))
                return
            temporary[cId] = True
            for nId in self.dgForward[cId]:
                visit(nId, cId)
            temporary[cId] = False
            permanent[cId] = True
            result.appendleft(cId)
        while 1:
            found = False
            for cId in range(self.n):
                if not permanent[cId]:
                    found = True
                    visit(cId, None)
            if not found:
                break
        self.dump("after removing cycles:")
        return list(result)

    def assignLayers(self):
        topsorted = self.topological_sort()
        node2layer = [None]*self.n
        # the layer index is the shortest path to one of the input nodes
        for cId in topsorted:
            l = None
            for pId in self.dgBackward[cId]:
                if (pId, cId) in self.cycleEdges:
                    continue
                assert node2layer[pId] is not None
                if l is None:
                    l = node2layer[pId] + 1
                l = max(l, node2layer[pId] + 1)
            node2layer[cId] = l if l is not None else 0
        layers = []
        for l in range(max(node2layer) + 1):
            layers.append([idx for idx in range(self.n) if node2layer[idx] == l])
        return layers, node2layer

    def sortLayers(self):
        def numberOfCrossings(layer1, layer2):
            res = 0
            for i,ni in enumerate(layer1):
                for nj in self.dgForward[ni]:
                    if (ni,nj) in self.cycleEdges or (ni,nj) in self.longEdges:
                        continue
                    j = layer2.index(nj)
                    for k, nk in enumerate(layer2):
                        for nh in self.dgBackward[nk]:
                            if (nh,nk) in self.cycleEdges or (nh,nk) in self.longEdges:
                                continue
                            h = layer1.index(nh)
                            if (h < i and k > j) or (h > i and k < j):
                                res += 1
            return res

        layers, node2layer = self.assignLayers()
        self.longEdges = set()
        # add virtual nodes for edges which span multiple layers
        for n1 in list(self.dgForward.keys()):
            for n2 in self.dgForward[n1].copy():
                if (n1,n2) in self.cycleEdges:
                    continue
                if node2layer[n2] != node2layer[n1]+1:
                    assert node2layer[n2] > node2layer[n1]+1
                    self.longEdges.add((n1, n2))
                    nc = n1
                    for l in range(node2layer[n1]+1, node2layer[n2]):
                        n = self.vn
                        self.vn += 1
                        node2layer.append(l)
                        layers[l].append(n)
                        self.dgForward[nc].add(n)
                        self.dgBackward[n] = set()
                        self.dgBackward[n].add(nc)
                        self.dgForward[n] = set()
                        nc = n
                    self.dgForward[nc].add(n2)
                    self.dgBackward[n2].add(nc)
        self.dump("after adding virtual nodes")
        nc = sum([numberOfCrossings(layers[i-1], layers[i]) for i in range(1, len(layers))])
        print("numCrosses before heuristic:", nc)
        # heuristic for rearranging the layer according to the average position of previous nodes
        numCrosses = 0
        for cl in range(1, len(layers)):
            averagePrevPos = []
            for cn in layers[cl]:
                prevPos = []
                for pn in self.dgBackward[cn]:
                    if (pn, cn) in self.cycleEdges or (pn,cn) in self.longEdges:
                        continue
                    prevPos.append(layers[cl-1].index(pn))
                averagePrevPos.append(sum(prevPos)/len(prevPos))
            initial_perm = sorted(list(range(len(layers[cl]))), key=lambda x: averagePrevPos[x])
            layers[cl] = [layers[cl][i] for i in initial_perm]
            numCrosses += numberOfCrossings(layers[cl-1], layers[cl])
        print("numCrosses after heuristic: ", numCrosses)
        # swap pairs until convergence
        for cl in range(len(layers)):
            def getNumCrosses(cLayer):
                return (numberOfCrossings(layers[cl-1], cLayer) if cl > 0 else 0 +
                        numberOfCrossings(cLayer, layers[cl+1]) if cl < len(layers) - 1 else 0)
            while 1:
                numCrosses = getNumCrosses(layers[cl])
                found = False
                for i in range(len(layers[cl])-1):
                    testL = layers[cl][:i] + [layers[cl][i+1],layers[cl][i]] + layers[cl][i+2:]
                    testCrosses = getNumCrosses(testL)
                    if testCrosses < numCrosses:
                        found = True
                        numCrosses = testCrosses
                        layers[cl] = testL
                if not found:
                    break
        numCrosses = sum([numberOfCrossings(layers[i-1], layers[i]) for i in range(1, len(layers))])
        return layers, numCrosses

    def layersToNodeNames(self, layers):
        res = []
        for l in layers:
            lr = []
            for n in l:
                if n in self.id2name:
                    lr.append(self.id2name[n])
            res.append(lr)
        return res

if __name__ == "__main__":
    import random
    import time

    t0 = time.time()
    random.seed(0)
    gr = GraphRep()
    numNodes = 15
    maxNumEdges = 3
    minNumEdges = 1
    for i in range(numNodes):
        gr.addNode(i)
    for i in range(numNodes):
        for k in range(random.randint(minNumEdges, maxNumEdges)):
            j = random.randint(0, numNodes-1)
            gr.addEdge(i,j)
    layers, numCrosses = gr.sortLayers()
    for l in layers:
        print(l)
    print("numCrosses", numCrosses)
    print("time spent: %.3s" % (time.time() - t0))