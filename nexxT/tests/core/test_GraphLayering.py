import random
import time
from nexxT.services.gui.GraphLayering import GraphRep

def test_smoke():
    t0 = time.time()
    random.seed(0)
    gr = GraphRep()
    numNodes = 15
    maxNumEdges = 3
    minNumEdges = 1
    for i in range(numNodes):
        gr.addNode(i)
    for i in range(numNodes):
        for _ in range(random.randint(minNumEdges, maxNumEdges)):
            j = random.randint(0, numNodes-1)
            gr.addEdge(i, j)
    layers, numCrosses = gr.sortLayers()
    assert numCrosses <= 24
    assert time.time() - t0 <= 0.5 # 0.5 seconds shall be more than enough
    assert len(layers) in [8,9,10,11,12,13,14] # we have 11 atm
    if 0:
        for l in layers:
            print(l)
        print("numCrosses", numCrosses)
        print("time spent: %.3s" % (time.time() - t0))

if __name__ == "__main__":
    test_smoke()