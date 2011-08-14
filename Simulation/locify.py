#!/usr/bin/python

##################
# locify.py
#
# Copyright David Baddeley, 2009
# d.baddeley@auckland.ac.nz
#
# This file may NOT be distributed without express permision from David Baddeley
#
# Generates a series of point/fluorophore positions from a given grayscale image
#
##################

from numpy.random import rand
import numpy as np
#import np.random


def locify(im, pixelSize=1, pointsPerPixel=0.1):
    '''Create a set of point positions with a density corresponding to the
    input image im. Useful for generating localisation microscopy images from
    conventional images. Assumes im is a 2D array with values between 0 and 1
    and interprets this value as a probability. pointsPerPixel gives the point density for a prob. of 1.'''

    #what range shold we generate points in
    xmax = im.shape[0]
    ymax = im.shape[1]

    #generate a number of candidate points based on uniform labelling
    #which will be accepted/rejected later
    numPoints = im.shape[0]*im.shape[1]*pointsPerPixel

    x = xmax*rand(numPoints) - .5
    y = ymax*rand(numPoints) - .5

    #index into array to get probability of acceptance
    p = im[x.round().astype('i'), y.round().astype('i')]

    #use monte-carlo to accept points with the given probability
    mcInd = rand(len(x)) < p

    #take subset of positions and scale to pixel size
    x = pixelSize*x[mcInd]
    y = pixelSize*y[mcInd]

    return (x,y)
    

def testPattern():
    '''generate a test pattern'''
    pass
    
fresultdtype=[('tIndex', '<i4'),('fitResults', [('A', '<f4'),('x0', '<f4'),('y0', '<f4'),('sigma', '<f4')]),('fitError', [('A', '<f4'),('x0', '<f4'),('y0', '<f4')])]

def FitResultR(x,y,I,t):
	r_I = np.sqrt(I)

        return np.array([(t, np.array([I, x, y], 'f'), np.array([r_I, 250/r_I, 250/r_I], 'f'))], dtype=fresultdtype)

def eventify(x,y,meanIntensity, meanDuration, backGroundIntensity, meanEventNumber, sf = 2, tm=2000):
    Is = np.random.exponential(meanIntensity, x.shape)
    Ns = np.random.poisson(meanEventNumber, x.shape)
    
    evts = []
    #t = 0

    for x_i, y_i, I_i, N_i in zip(x,y,Is,Ns):
        for j in range(N_i):
            duration = np.random.exponential(meanDuration)
            t = np.random.exponential(tm)

            #evts += [(x_i, y_i, I_i, t+k) for k in range(duration)] + [(x_i, y_i, I_i*(duration%1), t+floor(duration))]
            evts += [FitResultR(x_i, y_i, I_i, t+k) for k in range(duration)] + [FitResultR(x_i, y_i, I_i*(duration%1), t+np.floor(duration))]

    evts = np.vstack(evts)
    
    #xn, yn, In = evts[:,0], evts[:,1], evts[:,2]

    In = evts['fitResults']['A']

    detect = np.exp(-In**2/(2*sf**2*backGroundIntensity)) < np.random.uniform(size=In.shape)

    #xn = xn[detect]
    #yn = yn[detect]
    #In = In[detect]

    evts = evts[detect]

    s = evts['fitResults']['x0'].shape

    evts['fitResults']['x0'] = evts['fitResults']['x0'] + evts['fitError']['x0']*np.random.normal(size=s)
    evts['fitResults']['y0'] = evts['fitResults']['y0'] + evts['fitError']['y0']*np.random.normal(size=s)

    #filter

    return evts

    #return xn, yn, In