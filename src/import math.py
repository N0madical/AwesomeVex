import math

def calcDistanceFromPixels(offset):
    return ((offset/3)/math.tan(0.197))

print(calcDistanceFromPixels(60))