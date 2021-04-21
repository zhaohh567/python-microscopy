#!/usr/bin/python

###############
# BaseDataSource.py
#
# Copyright David Baddeley, 2012
# d.baddeley@auckland.ac.nz
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
################

import numpy as np
class DefaultList(list):
    """List which returns a default value for items not in the list"""
    def __init__(self, *args):
        list.__init__(self, *args)

    def __getitem__(self, index):
        try:
            return list.__getitem__(self, index)
        except IndexError:
            return 1


class BaseDataSource(object):
    @property
    def shape(self):
        """The 4D shape of the datasource"""
        #if self.type == 'DataSource':
        raise NotImplementedError
    
    @property
    def ndim(self):
        # for numpy (and dask) compatibility
        raise NotImplementedError
    
    @property
    def dtype(self):
        # for numpy (and dask) compatibility
        return self.getSlice(0).dtype
    
    @property
    def nbytes(self):
        return np.prod(self.shape) * self.getSlice(0).itemsize
    
    @property
    def is_complete(self):
        """
        For datasources which may be opened before spooling is finished.

        Over-ridden in derived classes (currently only ClusterPZFDataSource)

        Returns
        -------

        is_complete : bool
            has spooling of this series finished

        """
        return True
    
    def getSlice(self, ind):
        """Return the nth 2D slice of the DataSource where the higher dimensions
        have been flattened.

        equivalent to indexing contiguous 4D data with data[:,:,ind%data.shape[2], ind/data.shape[3]]

        e.g. for a 100x100x50x2 DataSource, getSlice(20) would return data[:,:,20,0].squeeze()
        whereas getSlice(75) would return data[:,:,25, 1].squeeze()
        """
        raise NotImplementedError
    
    def getSliceShape(self):
        """Return the 2D shape of a slice"""
        raise NotImplementedError
    
    def getNumSlices(self):
        """Return the number of 2D slices. This is the product of the
        dimensions > 2
        """
        raise NotImplementedError
    
    def getEvents(self):
        """Return any events which are ascociated with this DataSource"""
        raise NotImplementedError
    
    def __getitem__(self, keys):
        """Allows slicing into the DataSource as though it were a numpy ndarray.
        
        Behaviour is not guaranteed to be strictly 1:1 with numpy for missing dimensions (we are a bit more lenient)
        """
        
        raise NotImplementedError


class XYTCDataSource(BaseDataSource):
    """
    Old style data source base
    """
    oldData = None
    oldSlice = None
    #nTrueDims =3
    additionalDims = 'T'
    #sizeZ = 1
    sizeC = 1
    
    @property
    def nTrueDims(self):
        """The number of dimensions which are truely present within the data,
        rather than just faked"""
        return 2 + len(self.additionalDims)
    
    @property
    def shape(self):
        """The 4D shape of the datasource"""
        #if self.type == 'DataSource':
        return DefaultList(self.getSliceShape() + (int(self.getNumSlices()/self.sizeC),self.sizeC) )
    
    @property
    def ndim(self):
        # for numpy (and dask) compatibility
        return self.nTrueDims
        
    def __getitem__(self, keys):
        """Allows slicing into the DataSource as though it were a numpy ndarray.
        
        We ignore any dimensions higher than the dimensionaltyof the data.
        """
        keys = list(keys)
        #print keys
        for i in range(len(keys)):
            if not isinstance(keys[i], slice):
                if keys[i] == -1:
                    #special case for -1 indexing
                    keys[i] = slice(-1, None)
                else:
                    keys[i] = slice(keys[i],keys[i] + 1)
        if keys == self.oldSlice:
            return self.oldData
        self.oldSlice = keys
        #if len(keys) > len(self.data.shape):
        #    keys = keys[:len(self.data.shape)]
        #if self.dim_1_is_z:
        #    keys = [keys[2]] + keys[:2] + keys[3:]

        #print keys

        
        if self.nTrueDims <= 3 and not self.additionalDims == 'C': #x,y, z/t
            r = np.concatenate([np.atleast_2d(self.getSlice(i)[keys[0], keys[1]])[:,:,None] for i in range(*keys[2].indices(self.getNumSlices()))], 2)
        elif self.nTrueDims == 4 or self.additionalDims == 'C':
            #print keys[3]
            col_indices =  range(*keys[3].indices(self.shape[3]))
            #print col_indices
            r = []
            for c_i in col_indices:
                if self.additionalDims == 'TC':
                    indices = np.arange(*keys[2].indices(self.shape[2])) + c_i*self.shape[2]
                elif self.additionalDims == 'CT' or self.additionalDims == 'C':
                    indices = np.arange(*keys[2].indices(self.shape[2]))*self.shape[3] + c_i
                    

                r.append(np.concatenate([np.atleast_2d(self.getSlice(i)[keys[0], keys[1]])[:,:,None] for i in indices], 2))

            if len(r) > 1:
                r = np.concatenate([r_i[:,:,:,None] for r_i in r], 3)
            else:
                r = r[0]
            

        self.oldData = r

        return r
    
def _slice_len(s):
    return (s.stop - s.start) // s.step

class XYZTCDataSource(BaseDataSource):
    """ Datasource to use as a base class for datasources which are natively 5D (and can be used in isinstance checks to
    Test the above.
    """

    def __init__(self, input_order='XYZTC', size_z=1, size_t=1, size_c=1):
        self._input_order = input_order
    
        if not input_order.startswith('XY'):
            raise RuntimeError('First 2 dimensions of input must be X and Y')
    
        if input_order == 'XYZTC':
            self._z_stride = 1
            self._t_stride = size_z
            self._c_stride = size_z * size_t
        elif input_order == 'XYTZC':
            self._z_stride = size_t
            self._t_stride = 1
            self._c_stride = size_z * size_t
        elif input_order == 'XYZCT':
            self._z_stride = 1
            self._t_stride = size_z * size_c
            self._c_stride = size_z
        elif input_order == 'XYTCZ':
            self._z_stride = size_t * size_c
            self._t_stride = 1
            self._c_stride = size_t
        elif input_order == 'XYCZT':
            self._z_stride = size_c
            self._t_stride = size_c * size_z
            self._c_stride = 1
        elif input_order == 'XYCTZ':
            self._z_stride = size_t * size_c
            self._t_stride = size_c
            self._c_stride = 1
        else:
            raise RuntimeError('Input order: %s not supported' % input_order)
    
    @property
    def ndim(self):
        return  5
    
    def __getitem__(self, keys):
        keys = list(keys)
        
        if not len(keys) == 5:
            raise RuntimeError('Must provide a 5-dimensional slice')
        
        indices = {}
        
        for i in range(len(keys)):
            if not isinstance(keys[i], slice):
                if keys[i] == -1:
                    #special case for -1 indexing
                    keys[i] = slice(-1, None)
                else:
                    keys[i] = slice(keys[i], keys[i] + 1)
            
            indices['XYZTC'[i]] = keys[i].indices(self.shape[i])
        
        
        #print(indices)
        #allocate output array
        out = np.zeros([_slice_len(slice(*indices[k])) for k in 'XYZTC'], dtype=self.dtype)
        
        for ci, c in enumerate(range(*indices['C'])):
            for ti, t in enumerate(range(*indices['T'])):
                for zi, z in enumerate(range(*indices['Z'])):
                    slice_idx = self._c_stride * c + self._t_stride * t + self._z_stride * z
                    out[:, :, zi, ci, ti] = self.getSlice(slice_idx)[keys[0], keys[1]]
        
        return out
    


class XYZTCWrapper(XYZTCDataSource):
    """
    Wrapper to turn an XYTC Datasource into an XYZTC DataSource by remapping the slicing.
    """
    def __init__(self, datasource, input_order='XYZTC', size_z=1, size_t=1, size_c=1):
        self._datasource = datasource
        
        XYZTCDataSource.__init__(self, input_order=input_order, size_z=size_z, size_t=size_t, size_c=size_c)
        
        #print(self._datasource)
        #print(self._datasource.getSliceShape())
        
        self._shape = tuple(self._datasource.getSliceShape()) + (size_z, size_t, size_c)
        self._dtype = self._datasource.dtype
    
    @classmethod
    def auto_promote(cls, data):
        """Try to automatically promote a datasource, guessing what dimensionality it should have
        
        currently assume series with > 100 frames along z/t dimension are time series,
        series with <= 100 frames are s-stacks
        """

        if getattr(data, 'additionalDims', 'TC') == 'CT':
            dim_order = 'XYZCT'
            size_z = 1
            size_t = data.shape[2]
        else:
            dim_order = 'XYZTC'
    
            if data.shape[2] > 100:
                # assume time series
                size_z = 1
                size_t = data.shape[2]
            else:
                # assume z stack
                size_t = 1
                size_z = data.shape[2]

        return cls(data, input_order=dim_order, size_z=size_z,size_t=size_t, size_c=data.shape[3])
    
    @property
    def shape(self):
        return self._shape
    
    @property
    def dtype(self):
        return self._dtype
    
    def getSlice(self, ind):
        return self._datasource.getSlice(ind)
    
    def getSliceShape(self):
        return self._datasource.getSliceShape()
    
    def getNumSlices(self):
        return self._datasource.getNumSlices()
    
    def getEvents(self):
        return  self._datasource.getEvents()
    
    @property
    def is_complete(self):
        return self._datasource.is_complete()


class XYTCWrapper(XYTCDataSource):
    """
    Wrapper to turn an XYZTC Datasource into an XYTC DataSource by remapping the slicing.
    
    Flattens Z & T dimensions into one Z/T dimension. Generally only interesting for backwards compatibility
    """
    
    def __init__(self, datasource):
        self._datasource = datasource
        
        self.sizeC = datasource.shape[4]
        self.additionalDims = 'TC'
    
    def getSlice(self, ind):
        return self._datasource.getSlice(ind)
    
    def getSliceShape(self):
        return self._datasource.getSliceShape()

    def getNumSlices(self):
        return self._datasource.getNumSlices()
    
    def getEvents(self):
        return self._datasource.getEvents()
    
    @property
    def is_complete(self):
        return self._datasource.is_complete()
    