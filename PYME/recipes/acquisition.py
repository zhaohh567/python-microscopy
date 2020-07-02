
from .base import register_module, ModuleBase, OutputModule
from .traits import Input, Output, CStr, Int, DictStrAny, Bool, Float, ListFloat
import requests
import json
import numpy as np

@register_module('UpdateSpoolerSettings')
class UpdateSpoolerSettings(ModuleBase):
    """
    Updates the SpoolController settings. 

    NOTE - not the prefered way of changing spooler settings. The spool 
    controller can also be accessed through action-queue tasks, which has the 
    advantage that settings can be effectively associated with acquisition tasks
    based on `Nice` if not directly as key-word arguments to 
    SpoolController.start_spooling.
    
    Parameters
    ----------
    spool_controller_url : CStr
    settings : traits.DictStrAny
        Settings to apply to the spool controller. Must be json serializable. 
        See PYME.IO.SpoolController.info for example settings, at the time of
        writing they include
            method : str
                'File', 'Queue' (py2 only), or 'Cluster'. 
            hdf_compression_level: int
                pytables compression level, valid for file/queue methods only.
            z_stepped : bool
                flag to toggle z stepping or standard protocol during spool
            z_dwell : int
                number of frames to acquire at each z position for z-stepped 
                spools
            cluster_h5 : bool
                spool to single h5 file on cluster (True) or pzf files (False).
                Only relevant for `Cluster` method.
            pzf_compression_settings : dict
                see PYME.Acquire.HTTPSpooler
            protocol_name : str
                filename of the acquisition protocol to follow while spooling
    input_name : anything
        input will simply be piped to output
    output_name : anything
        input_name
    
    """
    input_name = Input('input')
    spool_controller_url = CStr('http://127.0.0.1:9394')
    settings = DictStrAny()
    output_name = Output('output')

    def execute(self, namespace):
        requests.post(self.spool_controller_url + '/settings', 
                      data=json.dumps(self.settings),
                      headers={'Content-Type': 'application/json'})
        
        namespace[self.output_name] = namespace[self.input_name]


@register_module('QueueAcquisitions')
class QueueAcquisitions(OutputModule):
    """
    Queue move-to and start-spool acquisition tasks for each input position
    using the ActionServer web wrapper queue_action endpoint.

    Parameters
    ----------
    input_positions : Input
        PYME.IO.tabular containing 'x' and 'y' coordinates in units of 
        nanometers
    action_server_url : CStr
        URL of the microscope-side action server process.
    spool_settings : DictStrAny
        settings to be passed to `PYME.Acquire.SpoolController.StartSpooling` as
        key-word arguments. Ones that make sense in the context of this recipe
        module include:
            max_frames : int
                number of frames to spool per series
            method : str
                'File', 'Queue' (py2 only), or 'Cluster'. 
            hdf_compression_level: int
                pytables compression level, valid for file/queue methods only.
            z_stepped : bool
                flag to toggle z stepping or standard protocol during spool
            z_dwell : int
                number of frames to acquire at each z position for z-stepped 
                spools
            cluster_h5 : bool
                spool to single h5 file on cluster (True) or pzf files (False).
                Only relevant for `Cluster` method.
            pzf_compression_settings : dict
                see PYME.Acquire.HTTPSpooler
            protocol_name : str
                filename of the acquisition protocol to follow while spooling
    lifo: Bool
        last-in first-out behavior (True) starts at the last position in 
        `input_positions`, False starts with the 0th. Useful in instances where
        e.g. you leave the microscope at the end of a detection scan and
        reversing the position order could mean less travel.
    optimize_path : Bool
        toggle whether acquisition tasks for positions are posted in an order
        which will minimize stage travel. Still respects the `lifo` parameter to
        pick the start.
    timeout : Float
        time in seconds after which the acquisition tasks associated with these
        positions will be ignored/unqueued from the action manager.
    """
    input_positions = Input('input')
    action_server_url = CStr('http://127.0.0.1:9393')
    spool_settings = DictStrAny()
    lifo = Bool(True)
    optimize_path = Bool(True)
    timeout = Float(np.finfo(float).max)
    nice_range = ListFloat()

    def save(self, namespace, context={}):
        """
        Parameters
        ----------
        namespace : dict
            The recipe namespace
        context : dict
            Information about the source file to allow pattern substitution to 
            generate the output name. At least 'basedir' (which is the fully 
            resolved directory name in which the input file resides) and 
            'filestub' (which is the filename without any extension) should be 
            resolved.
        """
        
        positions = np.stack((namespace[self.input_positions]['x'], 
                              namespace[self.input_positions]['y']), 
                              axis=1) / 1e3  # (N, 2), nm -> um

        if len(self.nice_range) == 2:
            nices = np.linspace(self.nice_range[0], self.nice_range[1], 
                                2 * len(positions))
        else:
            nices = np.arange(2 * len(positions))
        
        if self.optimize_path:
            from PYME.Analysis.points.traveling_salesperson import sort
            start = len(positions) if self.lifo else 0
            positions = sort.tsp_sort(positions, start)
        else:
            positions = positions[::-1, :] if self.lifo else positions
        
        dest = self.action_server_url + '/queue_action'
        for ri in range(positions.shape[0]):
            args = {'function_name': 'centre_roi_on', 
            'args': {'x': positions[ri, 0], 'y': positions[ri, 1]}, 
                    'timeout': self.timeout, 'nice': nices[2 * ri]}
            requests.post(dest, data=json.dumps(args), 
                          headers={'Content-Type': 'application/json'})
            
            args = {'function_name': 'spoolController.StartSpooling',
                    'args': self.spool_settings,
                    'timeout': self.timeout, 'nice': nices[2 * ri + 1]}
            requests.post(dest, data=json.dumps(args), 
                          headers={'Content-Type': 'application/json'})
