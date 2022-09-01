"""
Created on 26.07.2022

@author: Erik Altermann
@email: Erik.Altermann@tu-dortmund.de

"""

import logging
import numpy as np
import pyqtgraph.opengl as gl
import time 

from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QWidget
import PyQt5.QtCore as qtc

from ..data_classes.singletons import Settings


from .media_player import AbstractMediaPlayer

class MocapPlayer(AbstractMediaPlayer):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.media = MocapBackend()
        settings = Settings.instance()

        show_mocap_grid = settings.mocap_grid
        use_dynamic_mocap_grid = settings.mocap_grid_dynamic
        self.set_floor_grid(show_mocap_grid, use_dynamic_mocap_grid)
        
        self.media.right_mouse_btn_clicked.connect(self.open_context_menu)
        self.layout().addWidget(self.media)
        
    def load(self, input_file):
        self.media.load(input_file)
        self.n_frames = self.media.frames.shape[0]
        self.fps = 100
        self.media.set_position(0)
        self.loaded.emit(self)
        
    def update_media_position(self):
        pos = self.position + self.offset
        if 0 <= pos < self.n_frames:
            self.media.set_position(pos)
    
    def set_floor_grid(self, enable, dynamic):
        if self.media:
            self.media.set_floor_grid(enable, dynamic)
    

class MocapBackend(gl.GLViewWidget):
    right_mouse_btn_clicked = qtc.pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.number_samples = 0
        self.frames = None
        self.position = None
        
        self.DEFAULT_HEIGHT = -1
        self.grid_height = -1
        
        self.RESET_INTERVAL = 100
        self.reset_counter = 0

        self.dynamic_floor = False
        self.zgrid = gl.GLGridItem()
        #self.zgrid.translate(0, 0, self.DEFAULT_HEIGHT)
        self.addItem(self.zgrid)
        
        
        self.current_skeleton = gl.GLLinePlotItem(pos=np.array([[0, 0, 0], [0, 0, 0]]),
                                                  color=np.array([[0, 0, 0, 0], [0, 0, 0, 0]]),
                                                  mode='lines')
        self.addItem(self.current_skeleton)

    @pyqtSlot(str, bool)
    def load(self, path, normalize=True):
        try:
            if normalize:
                array = np.loadtxt(path, delimiter=',', skiprows=5)
                array = array[:, 2:]
                # normalizing
                normalizing_vector = array[:, 66:72]  # 66:72 are the columns for lowerback
                for _ in range(21):
                    normalizing_vector = np.hstack((normalizing_vector, array[:, 66:72]))
                array = np.subtract(array, normalizing_vector)
            else:
                array = np.loadtxt(path, delimiter=',', skiprows=1)
                array = array[:, 2:]

            self.mocap_data = array
            self.number_samples = self.mocap_data.shape[0]

            # Calculate Skeleton
            frames = np.zeros((self.number_samples, 44, 3))  # dimensions are( frames, bodysegments, xyz)
            for frame_index in range(self.number_samples):
                frame = array[frame_index, :]
                frame = calculate_skeleton(frame)
                frames[frame_index, :, :] = frame

            self.frames = frames
        except Exception as e:
            raise e

    @pyqtSlot(int)
    def set_position(self, new_pos):
        start = time.time()
        self.position = new_pos # update position
        skeleton = self.get_current_skeleton() # update skeleton
        # skeleton = self.frames[self.position]
        self.current_skeleton.setData(pos=skeleton, color=np.array(skeleton_colors), width=4, mode='lines')
        #self.update_grid() # update grid
        end = time.time()
        # logging.info('SET_POSITION TOOK {}'.format(end - start ))
    
    def get_current_skeleton(self):
        start = time.time()
        skeleton = self.frames[self.position]
        if self.dynamic_floor:            
            height = 0
            for segment in [body_segments_reversed[i] for i in ['L toe', 'R toe', 'L foot', 'R foot']]:
                    segment_height = skeleton[segment * 2, 2]
                    height = min((height, segment_height))
            skeleton = skeleton - height
        end = time.time()
        # logging.info('get_current_skeleton TOOK {}'.format(end - start))
        return skeleton
        
    def update_grid(self):
        
        start = time.time()
        self.reset_counter += 1
        if self.reset_counter >= self.RESET_INTERVAL:
            self.reset_grid_location()
            self.reset_counter = 0
        if self.zgrid.visible():            
            if self.dynamic_floor:
                height = 0
                skeleton = self.frames[self.position]
                for segment in [body_segments_reversed[i] for i in ['L toe', 'R toe', 'L foot', 'R foot']]:
                    segment_height = skeleton[segment * 2, 2]
                    height = min((height, segment_height))
            else:
                height = self.DEFAULT_HEIGHT
            
            height_delta = height - self.grid_height
            self.grid_height = height
            self.zgrid.translate(0, 0, height_delta)
            
            
        end = time.time()
        logging.info('update_grid TOOK {}'.format(end - start))
            
    def reset_grid_location(self):
        self.zgrid.resetTransform()
        self.zgrid.translate(0,0, self.DEFAULT_HEIGHT)
        self.grid_height = -1
    
    def mousePressEvent(self, ev):
        lpos = ev.position() if hasattr(ev, 'position') else ev.localPos()
        self.mousePos = lpos
        if ev.button() == qtc.Qt.RightButton:
            self.right_mouse_btn_clicked.emit()

    @pyqtSlot(bool, bool)
    def set_floor_grid(self, enable, dynamic):
        self.zgrid.setVisible(enable)
        # only update if needed
        if dynamic != self.dynamic_floor:
            self.dynamic_floor = dynamic
            if self.position:
                self.set_position(self.position)


body_segments = {
    -1: 'none',
    0: 'head',
    1: 'head end',
    2: 'L collar', 12: 'R collar',
    6: 'L humerus', 16: 'R humerus',
    3: 'L elbow', 13: 'R elbow',
    9: 'L wrist', 19: 'R wrist',
    10: 'L wrist end', 20: 'R wrist end',
    11: 'lower back',
    21: 'root',
    4: 'L femur', 14: 'R femur',
    7: 'L tibia', 17: 'R tibia',
    5: 'L foot', 15: 'R foot',
    8: 'L toe', 18: 'R toe'}

body_segments_reversed = {v: k for k, v in body_segments.items()}

colors = {'r': (1, 0, 0, 1), 'g': (0, 1, 0, 1), 'b': (0, 0, 1, 1), 'y': (1, 1, 0, 1)}

# each bodysegmentline needs 2 colors because each has a start and end.
# different colors on each end result in a gradient
skeleton_colors = (
    colors['b'], colors['b'],  # head
    colors['b'], colors['b'],  # head end
    colors['b'], colors['b'],  # L collar
    colors['g'], colors['g'],  # L elbow
    colors['r'], colors['r'],  # L femur
    colors['r'], colors['r'],  # L foot
    colors['g'], colors['g'],  # L humerus
    colors['r'], colors['r'],  # L tibia
    colors['r'], colors['r'],  # L toe
    colors['g'], colors['g'],  # L wrist
    colors['g'], colors['g'],  # L wrist end
    colors['b'], colors['b'],  # lower back
    colors['b'], colors['b'],  # R collar
    colors['g'], colors['g'],  # R elbow
    colors['r'], colors['r'],  # R femur
    colors['r'], colors['r'],  # R foot
    colors['g'], colors['g'],  # R humerus
    colors['r'], colors['r'],  # R tibia
    colors['r'], colors['r'],  # R toe
    colors['g'], colors['g'],  # R wrist
    colors['g'], colors['g'],  # R wrist end
    colors['b'], colors['b'],  # root
)


def calculate_skeleton(frame: np.array) -> np.array:
    """Calculates the lines indicating positions of bodysegments at a single timestep

    Arguments:
    ---------
    frame_index : int
        an integer between 0 and self.number_samples
        denotes the frame/timestep at which the skeleton should be calculated
    ---------

    Returns:
    ---------
    array : numpy.array
        2D array with shape (44,3).
        Contains 44 3-Tupels or 3D coordinates.
        Each bodysegment gets 2 coordinates, for a start and  an end point.
        There are 22 bodysegments.
    ---------

    """

    # Extraction of Translational data for each bodysegment (source)
    tx = []
    ty = []
    tz = []
    for i in range(22):
        tx.append(frame[i * 6 + 3])
        ty.append(frame[i * 6 + 4])
        tz.append(frame[i * 6 + 5])

    # Extraction of Translational data for each bodysegment (target)
    tu = []  # corresponds to x coordinates
    tv = []  # corresponds to y coordinates
    tw = []  # corresponds to z coordinates
    offset = 3
    for coords in [tu, tv, tw]:  # xyz        ->     uvw
        coords.append(frame[2 * 6 + offset])  # 0   head      -> l collar/rcollar
        coords.append(frame[0 * 6 + offset])  # 1   head end  -> head
        coords.append(frame[11 * 6 + offset])  # 2 l collar    -> lowerback
        coords.append(frame[6 * 6 + offset])  # 3 l elbow     -> l humerus
        coords.append(frame[21 * 6 + offset])  # 4 l femur     -> root
        coords.append(frame[7 * 6 + offset])  # 5 l foot      -> l tibia
        coords.append(frame[2 * 6 + offset])  # 6 l humerus   -> l collar
        coords.append(frame[4 * 6 + offset])  # 7 l tibia     -> l femur
        coords.append(frame[5 * 6 + offset])  # 8 l toe       -> l foot
        coords.append(frame[3 * 6 + offset])  # 9 l wrist     -> l elbow
        coords.append(frame[9 * 6 + offset])  # 10 l wrist end -> l wrist
        coords.append(frame[11 * 6 + offset])  # 11   lowerback -> lowerback
        coords.append(frame[11 * 6 + offset])  # 12 r collar    -> lowerback
        coords.append(frame[16 * 6 + offset])  # 13 r elbow     -> r humerus
        coords.append(frame[21 * 6 + offset])  # 14 r femur     -> root
        coords.append(frame[17 * 6 + offset])  # 15 r foot      -> r tibia
        coords.append(frame[12 * 6 + offset])  # 16 r humerus   -> r collar
        coords.append(frame[14 * 6 + offset])  # 17 r tibia     -> r femur
        coords.append(frame[15 * 6 + offset])  # 18 r toe       -> r foot
        coords.append(frame[13 * 6 + offset])  # 19 r wrist     -> r elbow
        coords.append(frame[19 * 6 + offset])  # 20 r wrist end -> r wrist
        coords.append(frame[11 * 6 + offset])  # 21   root      -> lowerback
        offset += 1

    # combine the 3 lists of source coordinates into a 3-tupel list
    txyz = list(zip(tx, ty, tz))
    # combine the 3 lists of target coordinates into a 3-tupel list
    tuvw = list(zip(tu, tv, tw))
    # append the coordinates from source and target alternatingly to a single list
    t_all = []
    for a, b in zip(txyz, tuvw):
        t_all.append(a)
        t_all.append(b)

    # convert the list into an array, convert millimeters to meters and return the result
    return np.array(t_all) / 1000

