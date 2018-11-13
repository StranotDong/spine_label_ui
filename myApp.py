#get_ipython().run_line_magic('matplotlib', 'qt')
import SimpleITK as sitk
import PyQt5
import matplotlib.pyplot as plt
plt.switch_backend('qt5Agg')
# import ipywidgets as widgets
from IPython.display import display

from os.path import exists, join
import os
import csv
import sys

from PyQt5.QtWidgets import *#QDialog, QApplication, QPushButton, QVBoxLayout, QRadioButton
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5 import QtCore, Qt

from namerules import nameRules
# from qrangeslider import QRangeSlider

nr = nameRules()

'''
A decorator function to skip the unreadable images and display the new image
'''
def display_decor( func ):
    def wrapper(*args):
        self = args[0]
        oriImgPointer = self.ImgPointer
        func(self)
        curImgPointer = self.ImgPointer
        while self.ReadableStatusDict[self.ImgIDList[self.ImgPointer]] == nr.unreadable:
            func(self)
            if self.ImgPointer == curImgPointer:
                self.ImgPointer = oriImgPointer
                return
        self.init_display()
#        print(self.ImgPointer)
    return wrapper

'''
A decorator function to change the save_status_label to unsaved
'''
def unsave_decor(func):
    def wrapper(*args):
        self = args[0]
        func(self)
        self.save_status = nr.unsaved
        self.update_save_status_label()
    return wrapper



class SpineLabellingApp(QDialog):
    """
    Init:
        Input:
            img_root_dir: the root directory that contains all the images
            ImgIDList: A list that contains alle image IDs. IDs are the paths of the images
            fpath: The csv file path to store the results
            figure_resolution: the resolution of the image that will be displayed
            begin: The image that firstly shown.
                   An integer to point out the position in ImageIDList
                   Default is None, i.e, the next unlabelled image.
            zoom_base_scale: used when zooming, default is 2
            wl_sacle: used when window level changing, default is 0.5
            debug_mode: whether the class is in debugging, if it is, a debug button will appear
    """
    def __init__(self,
                 img_root_dir,
                     ImgIDList,
                 fpath,
                 begin=None,
                 zoom_base_scale=1.2,
                 wl_scale=0.3,
                 debug_mode=False,
                parent=None,
                **kw):
        QDialog.__init__(self, parent)

        self.VBLabelList = nr.VBLabelList
        self.CoordTypeList = nr.CoordTypeList # center vs corner
        self.CoordType = self.CoordTypeList[0]

        self.img_root_dir = img_root_dir
        self.ImgIDList = ImgIDList
        self._get_ImgFullPathList()
        self.fpath = fpath

        self.zoom_base_scale = zoom_base_scale
        self.wl_scale = wl_scale
        self.debug_mode = debug_mode

        self.VBPointer = 0 # the current processed VB, init as L1          
        self.mode = nr.edit # current mode: edit or view
        self.save_status = nr.saved
        self.init_display_flag = True

        self.is_update_table = False
        self.usrnm_temp_file = nr.temp_filename
    # layout management
        self.columnStretch = [1,10,3]
#        self.rowStretch = [8,2]
        self.screen = QDesktopWidget().screenGeometry(-1)
        self.resize(self.screen.width(), self.screen.height())
        image_width_scale = self.columnStretch[1] / (self.columnStretch[0] + self.columnStretch[1] +self.columnStretch[2]) 
#        image_height_scale = self.rowStretch[0] / (self.rowStretch[0] + self.rowStretch[1]) 
#        self.figure_resolution = (self.screen.width()*image_width_scale, self.screen.height()*image_height_scale)

        self.figure_resolution = (self.screen.width()*image_width_scale, self.screen.height())
    # (1) Read the csv file to construct the StoreDict
        ## StoreDict is a dict storing all the results, the structure is
        ## {ImageIDList: {VBLabels: {Coord: (x,y), Fracture:??}}}
        ## status includes U (for untouched), T (for touched)
        self.dict_constructor()

        # (2) The first image that will be shown
        # self.ImgPointer is always pointing to the image that is shown currently
        self.ImgPointer = 0
        if begin != None:
            self.ImgPointer = begin
        else:
            for index, ID in enumerate(self.ImgIDList):
                if self.StatusDict[ID] == nr.untouch and self.ReadableStatusDict[ID] == nr.readable:
                    self.ImgPointer = index
                    break

        # (3) A place for the image
#            self.Figure = plt.figure()
        self.fig, self.axes = plt.subplots(1,1)
        self.dpi = self.fig.dpi
        self.figure_size = (self.figure_resolution[0]/self.dpi, self.figure_resolution[1]/self.dpi)
        self.fig.set_size_inches(self.figure_size)
#            assert fig.dpi == self.fig.dpi


        # (4) Display the start UI
        self.start_ui()

    """
    Get the full Image file path
    """
    def _get_ImgFullPathList(self):
        #########################################################################
#            self.ImgFullPathList = [None for i in range(len(self.ImgIDList))]
#            for root, dirs, files in os.walk(self.img_root_dir):        
#                for file in files:            
#                    i = self.ImgIDList.index(file)
#                    self.ImgFullPathList[i] = join(root,file)
        #########################################################################
        self.ImgFullPathList = self.ImgIDList



    """
    Construct the empty dicts
    """
    def _empty_dicts(self):
        self.StoreDict = {}
        self.StatusDict = {}
        self.ControversialDict = {}
        self.ReadableStatusDict = {}
        for ID in self.ImgIDList:
            VBDict = dict((vb, {nr.Coords:(None,None), nr.CorCoords:(None,None), nr.Fracture: nr.normal}) \
                       for vb in self.VBLabelList)
            self.StoreDict[ID] = VBDict
            self.StatusDict[ID] = nr.untouch
            self.ControversialDict[ID] = {nr.Modifier:None, nr.ConPart:'', nr.ConStatus:nr.uncontroversial}
            self.ReadableStatusDict[ID] = nr.readable
#            print(self.StoreDict, self.StatusDict)


    """
    Read the csv file and construct StoreDict and Status Dict
    """
    def dict_constructor(self):
        self._empty_dicts()
        if exists(self.fpath):
            with open(self.fpath) as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    if row[nr.head_status] != '':
                        self.StatusDict[row[nr.head_imgID]] = row[nr.head_status]
                    if row[nr.head_cenX] != '' and row[nr.head_cenY] != '':
                        self.StoreDict[row[nr.head_imgID]][row[nr.head_vbLabel]][nr.Coords] = (float(row[nr.head_cenX]), float(row[nr.head_cenY]))
                    if row[nr.head_corX] != '' and row[nr.head_corY] != '':
                        self.StoreDict[row[nr.head_imgID]][row[nr.head_vbLabel]][nr.CorCoords] = (float(row[nr.head_corX]), float(row[nr.head_corY]))
                    if row[nr.head_frac] != '':
                        self.StoreDict[row[nr.head_imgID]][row[nr.head_vbLabel]][nr.Fracture] = row[nr.head_frac]
                    if row[nr.head_modifier] != '':
                        self.ControversialDict[row[nr.head_imgID]][nr.Modifier] = row[nr.head_modifier]
                    
                    if row[nr.head_conParts] != '':
                        self.ControversialDict[row[nr.head_imgID]][nr.ConPart] = row[nr.head_conParts]
                    if row[nr.head_conStatus] != '':
                        self.ControversialDict[row[nr.head_imgID]][nr.ConStatus] = row[nr.head_conStatus]
                    if row[nr.head_readableStatus] != '':
                        self.ReadableStatusDict[row[nr.head_imgID]] = row[nr.head_readableStatus]
#            print(self.StoreDict, self.StatusDict)

    """
    starting ui
    """
    def start_ui(self):
        # Create the active UI components. Height and width are specified in 'em' units. This is
        # a html size specification, size relative to current font size        
        self.textbox = QLineEdit()
        if exists(self.usrnm_temp_file):
            with open(self.usrnm_temp_file, 'r') as f:
                temp = f.read()
                if temp != '':
                    self.textbox.setText(temp)
        self.start_button = QPushButton('START')
        self.start_button.clicked.connect(self.start)
        self.start_layout = QVBoxLayout()
#            self.mylayout = QVBoxLayout()
        self.start_layout.addWidget(self.textbox)
        self.start_layout.addWidget(self.start_button)
        self.mylayout = QVBoxLayout()
        self.mylayout.addLayout(self.start_layout)
        self.setLayout(self.mylayout)


    def _clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clearLayout(item.layout())


    """
    The function of click button
    """
    def start(self):
#        self.mylayout.removeWidget(self.textbox)
#        self.mylayout.removeWidget(self.start_button)
        if self.textbox.text() == '':
            QMessageBox.question(self, 'Username', 'Please enter a username', QMessageBox.Ok, QMessageBox.Ok)
            return
        self.username = self.textbox.text()
        with open(self.usrnm_temp_file,  'w+') as usrnm_file:
            usrnm_file.write(self.username)

        self._clearLayout(self.start_layout)
        self.start_button.deleteLater()
        self.start_button = None
        self.press = None
        self.key_press = None
        
        # basic framework of the UI
        #  ___________________
        # |__________________| up_lever: toolbar & wl_slider
        # |                |    | mid_level: left: canvas
        # |_____________|____| mid_level: right: basic widgets
        # |__________________| low_level: storing table
        self.canvas = FigureCanvas(self.fig)    
        self.canvas.setFocusPolicy( QtCore.Qt.ClickFocus )
        self.canvas.setFocus()
        self.toolbar = NavigationToolbar(self.canvas, self)
#            self.up_layout = QVBoxLayout()
#            self.up_layout.addWidget(self.toolbar)
#            self.mylayout.addLayout(self.up_layout)
        self.mid_layout = QHBoxLayout()
        self.mid_layout.addWidget(self.canvas)
        self.mylayout.addLayout(self.mid_layout)
        self.setLayout(self.mylayout)
        
        # Connect the mouse button press to the canvas
        self.fig.canvas.mpl_connect('button_press_event', self.image_click)
        # Connect the scoll event with zooming
        self.fig.canvas.mpl_connect('scroll_event',self.scoll_zoom)
        # Connect the mouse motion event
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        self.fig.canvas.mpl_connect('key_release_event', self.on_key_release)
        
        ui = self.create_ui()
        display(ui)
        self.init_display()
        self.showMaximized()
    
    
    """
    Display the current image
    """
    def init_display(self):
        self.init_display_flag = True
        self.VBPointer = 0
        # Get the grey value of the image as a numpy array
        self.img = sitk.ReadImage(self.ImgFullPathList[self.ImgPointer])[:,:,0]
        self.npa = sitk.GetArrayViewFromImage(self.img)
        self.min_intensity = self.npa.min()
        self.max_intensity = self.npa.max()
        self.cur_min_intensity = self.min_intensity
        self.cur_max_intensity = self.max_intensity
#            print(self.min_intensity, self.max_intensity)
#            self._wl_slider_builder(self.min_intensity, self.max_intensity)

        ## show the image
        self.axes.imshow(self.npa,
                         cmap=plt.cm.Greys_r,
                         vmin=self.min_intensity,
                         vmax=self.max_intensity,
                        )
        self.axes.set_xlim(0,len(self.npa[0]))
        self.axes.set_ylim(len(self.npa),0)

        cur_image = self.ImgIDList[self.ImgPointer]
        if self.ControversialDict[cur_image][nr.Modifier] != None and  self.ControversialDict[cur_image][nr.Modifier] != self.username:
            self.mode_radiobuttons2.setChecked(True)
        else:
            self.mode_radiobuttons1.setChecked(True)
        self.update_status()
        self.update_controversial_ui()
        self.update_display()
        self.table.setCurrentIndex(0)
        self.update_table()
        self.update_coord_tabs()
        self.update_frac_vb_label()
        self.update_save_status_label()
        plt.tight_layout()
        self.init_display_flag = False


    """
    Update the display if there is any operation
    """
    def update_display(self):
        # We want to keep the zoom factor which was set prior to display, so we log it before
        # clearing the axes.
        xlim = self.axes.get_xlim()
        ylim = self.axes.get_ylim()
        # Draw the image and localized points.
        self.axes.clear()
        self.axes.imshow(self.npa,
                         cmap=plt.cm.Greys_r,
                         vmin=self.cur_min_intensity,
                         vmax=self.cur_max_intensity)
        # Positioning the text is a bit tricky, we position relative to the data coordinate system, but we
        # want to specify the shift in pixels as we are dealing with display. We therefore (a) get the data 
        # point in the display coordinate system in pixel units (b) modify the point using pixel offset and
        # transform back to the data coordinate system for display.
        text_x_offset = 6
        text_y_offset = -8
        text_font = 6
        cur_imgID = self.ImgIDList[self.ImgPointer]
        marker_size = 40

        # center coords
        co = len(self.VBLabelList) # count of the center points
        for vb in self.VBLabelList:
            if self.StoreDict[cur_imgID][vb][nr.Fracture] == nr.normal:
                color = 'yellow'
            elif self.StoreDict[cur_imgID][vb][nr.Fracture] == nr.ost:
                color = 'orange'
            elif self.StoreDict[cur_imgID][vb][nr.Fracture] == nr.non_ost:
                color = 'green'
            pnt = self.StoreDict[cur_imgID][vb][nr.Coords]
            if pnt[0] == None or pnt[1] == None:
                co -= 1
                continue
            self.axes.scatter(pnt[0], pnt[1], s=marker_size, marker='+', color=color)
            # Get point in pixels.
            text_in_data_coords = self.axes.transData.transform([pnt[0],pnt[1]])
            # Offset in pixels and get in data coordinates.
            text_in_data_coords = self.axes.transData.inverted().\
                transform((text_in_data_coords[0]+text_x_offset, text_in_data_coords[1]+text_y_offset))
            self.axes.text(text_in_data_coords[0], text_in_data_coords[1], vb, color=color, fontsize=text_font)
        # corner coords
        cor_co = len(self.VBLabelList) # count of the corner points
        for vb in self.VBLabelList:
            if self.StoreDict[cur_imgID][vb][nr.Fracture] == nr.normal:
                color = 'yellow'
            elif self.StoreDict[cur_imgID][vb][nr.Fracture] == nr.ost:
                color = 'orange'
            elif self.StoreDict[cur_imgID][vb][nr.Fracture] == nr.non_ost:
                color = 'green'
            pnt = self.StoreDict[cur_imgID][vb][nr.CorCoords]
            if pnt[0] == None or pnt[1] == None:
                cor_co -= 1
                continue
            self.axes.scatter(pnt[0], pnt[1], s=marker_size, marker='*', color=color)
            # Get point in pixels.
            text_in_data_coords = self.axes.transData.transform([pnt[0],pnt[1]])
            # Offset in pixels and get in data coordinates.
            text_in_data_coords = self.axes.transData.inverted().\
                transform((text_in_data_coords[0]+text_x_offset, text_in_data_coords[1]+text_y_offset))
            self.axes.text(text_in_data_coords[0], text_in_data_coords[1], vb, color=color, fontsize=text_font)

        self.axes.set_title('localized {0} center points, {1} corner points'.format(co, cor_co))
        if not self.debug_mode:
            self.axes.set_axis_off()


        # Set the zoom factor back to what it was before we cleared the axes, and rendered our data.
        self.axes.set_xlim(xlim)
        self.axes.set_ylim(ylim)


        self.fig.canvas.draw_idle()


    """
    Update the table
    """
    def update_table(self):
        self.is_update_table = True
        cur_imgID = self.ImgIDList[self.ImgPointer]
#            cur_VB = self.VBLabelList[self.VBPointer]
        cur_sdict = self.StoreDict[cur_imgID]
        origin_imgpointer = self.VBPointer

        for i, vb in enumerate(self.VBLabelList):
            self.VBPointer = i
            if cur_sdict[vb][nr.Coords][0] != None:
                self.X_Label[i].setText(str(cur_sdict[vb][nr.Coords][0]))
            else:
                self.X_Label[i].setText('None')
            if cur_sdict[vb][nr.Coords][1] != None:
                self.Y_Label[i].setText(str(cur_sdict[vb][nr.Coords][1]))
            else:
                self.Y_Label[i].setText('None')
            if cur_sdict[vb][nr.CorCoords][0] != None:
                self.cor_X_Label[i].setText(str(cur_sdict[vb][nr.CorCoords][0]))
            else:
                self.cor_X_Label[i].setText('None')
            if cur_sdict[vb][nr.CorCoords][1] != None:
                self.cor_Y_Label[i].setText(str(cur_sdict[vb][nr.CorCoords][1]))
            else:
                self.cor_Y_Label[i].setText('None')
            if cur_sdict[vb][nr.Fracture] != None:
                if cur_sdict[vb][nr.Fracture] == nr.normal:
                    self.frac_rb1[i].setChecked(True)
                elif cur_sdict[vb][nr.Fracture] == nr.ost:
                    self.frac_rb2[i].setChecked(True)
                elif cur_sdict[vb][nr.Fracture] == nr.non_ost:
                    self.frac_rb3[i].setChecked(True)
            else:
                self.frac_rb1[i].setChecked(True)
#                self.frac[i].value = cur_sdict[vb][nr.Fracture]
        self.VBPointer = origin_imgpointer
        self.is_update_table = False

    """
    update the status dict
    """
    def update_status(self):
        cur_imgID = self.ImgIDList[self.ImgPointer]
        cur_sdict = self.StoreDict[cur_imgID]

        flag = False
        for vb in self.VBLabelList:
            if cur_sdict[vb][nr.Coords][0] != None \
                or cur_sdict[vb][nr.Coords][1] != None \
                or cur_sdict[vb][nr.CorCoords][0] != None \
                or cur_sdict[vb][nr.CorCoords][1] != None:
#                    or cur_sdict[vb][nr.Fracture] != None:
                self.StatusDict[cur_imgID] = nr.touch
                flag = True
                break

        if not flag:
            self.StatusDict[cur_imgID] = nr.untouch

        # update the status label in the UI
        if self.StatusDict[cur_imgID] == nr.untouch:
            status_text = 'untouched'
        else:
            status_text = 'touched'
        self.status_label.setText('Status:\n'+status_text)
        # update the num_labelled label in the UI
        num_u = 0
        for ID in self.ImgIDList:
            if self.StatusDict[ID] == nr.untouch:
                num_u += 1

        self.num_labelled_label.setText('Untouched/Total:\n'+str(num_u)+'/'+str(len(self.ImgIDList)))
        self.ImgeID_label.setText('Image '+str(self.ImgPointer+1)+':\n'+self.ImgIDList[self.ImgPointer])

        # updaet last modifier label
        text = 'Last Modifier:\n'
        if self.ControversialDict[cur_imgID][nr.Modifier] != None:
            text += self.ControversialDict[cur_imgID][nr.Modifier] 
        else:
            text += 'None'
        self.modifier_label.setText(text)



    '''
    update controversial ui
    '''
    def update_controversial_ui(self):
        cur_imgID = self.ImgIDList[self.ImgPointer]
        # update controversial label
        if self.ControversialDict[cur_imgID][nr.ConStatus] == nr.controversial:
            self.controversial_label.setText('Is this image controversial?\nYes')
            self.controversial_label.setStyleSheet('color: red')
        else:
            self.controversial_label.setText('Is this image controversial?\nNo')
            self.controversial_label.setStyleSheet('color: black')
            

        # updaet comment label
        if self.ControversialDict[cur_imgID][nr.ConPart] != '':
            self.comment_label.setText('Comments:\n'+ self.ControversialDict[cur_imgID][nr.ConPart])
        else:
            self.comment_label.setText('')
        # update textbox
        self.comment_textbox.setText('')



    """
    update coord tabs
    """
    def update_coord_tabs(self):
        cur_imgID = self.ImgIDList[self.ImgPointer]
        cur_sdict = self.StoreDict[cur_imgID]
        cur_vb = self.VBLabelList[self.VBPointer]
        if cur_sdict[cur_vb][nr.Coords][0] == None or cur_sdict[cur_vb][nr.Coords][1] == None:
            self.CoordType = self.CoordTypeList[0]
            self.coords_tables[self.VBPointer].setCurrentIndex(0)
        else:
            self.CoordType = self.CoordTypeList[1]
            self.coords_tables[self.VBPointer].setCurrentIndex(1)
            

    """
    update fracture VB lable
    """
    def update_frac_vb_label(self):
        cur_imgID = self.ImgIDList[self.ImgPointer]
        cur_sdict = self.StoreDict[cur_imgID]

        text_ost = ''
        text_normal = ''
        text_nonost = ''
        for i, vb in enumerate(self.VBLabelList):
            if cur_sdict[vb][nr.Fracture] == nr.ost:
                text_ost += vb + '\t'
            elif cur_sdict[vb][nr.Fracture] == nr.normal:
                text_normal += vb + '\t'
            elif cur_sdict[vb][nr.Fracture] == nr.non_ost:
                text_nonost += vb + '\t'
        self.frac_vb_label.setText(text_ost)
        self.normal_vb_label.setText(text_normal)
        self.nonost_vb_label.setText(text_nonost)


    '''
    update save status label
    '''
    def update_save_status_label(self):
        if self.save_status == nr.saved:
            color = 'black'
        else:
            color = 'red'
        self.save_status_label.setText(self.save_status)
        self.save_status_label.setStyleSheet('color: '+ color)

            
    """
    basic ui component
    """
    def _basic_components(self):
        self._unreadable_button_builder()
        self._mode_radiobuttons_builer()
        self._storing_tabs_builder()
        self._status_label_builder()
        self._controversial_ui_builder()
        self._button_builder('prev')
        self._button_builder('next')
        self._button_builder('prevun')
        self._button_builder('nextun')
        self._button_builder('clear')
        self._button_builder('clearall')
        self._button_builder('home')
        self._button_builder('save')


    """
    create UI
    """
    def create_ui(self):
        self._basic_components()
        self.operation_ui()
        self.labelling_ui()
        self.mid_layout.addLayout(self.labelling_layout)
        self.mid_layout.insertLayout(0,self.operation_layout)
#        for i, s in enumerate(self.rowStretch):
#            self.mid_layout.setStretch(i,s)
        # self.mylayout.addWidget(self.table)

        for i, s in enumerate(self.columnStretch):
             self.mylayout.setStretch(i, s)

        self.setLayout(self.mylayout)

    def labelling_ui(self):
        self.labelling_layout = QVBoxLayout()
        self.save_status_label = QLabel(self.save_status)
        self._frac_label_gather_box_builder()
        self.labelling_layout.addWidget(self.table)
        self.labelling_layout.addLayout(self.frac_label_gather_box)
        self.labelling_layout.addWidget(self.save_status_label)
        self.labelling_layout.setStretch(0,40)
        self.labelling_layout.setStretch(1,18)
        self.labelling_layout.setStretch(2,1)

    def operation_ui(self):
        # edit/view radiobuttons
        self.operation_layout = QVBoxLayout()
#        self.operation_layout.addWidget(self.mode_radiobuttons1)
#        self.operation_layout.addWidget(self.mode_radiobuttons2)
        self.operation_layout.addWidget(self.unreadable_button)
        self.operation_layout.addLayout(self.mode_vbox)
        # press buttons
        self._button_grid()
        self.operation_layout.addLayout(self.button_grid)
        # status box
        self.operation_layout.addLayout(self.status_box)
        self.operation_layout.addLayout(self.controversial_box)

    '''
    set unreadable button
    '''
    def _unreadable_button_builder(self):
        self.unreadable_button = QPushButton('set Unreadable')
        self.unreadable_button.clicked.connect(self.unreadable_button_on_click)


    '''
    function of unreadable button
    '''
    def unreadable_button_on_click(self):
        self._readable_status_dialog()

    
    '''
    the dialog that appear after click unreadable button
    '''
    def _readable_status_dialog(self):
        self.readable_dialog = QDialog()
        self.readable_dialog.setWindowTitle('Set Unreadable  Alert!')
        dlabel = QLabel('By setting the image unreadabl, the image will never show up again. Are you sure you what to set unreadable?')
        self.rdNoButton = QPushButton('No')
        self.rdNoButton.clicked.connect(self.readable_dialog.reject)
        self.rdYesButton = QPushButton('Yes')
        self.rdYesButton.clicked.connect(self._readable_dialog_yes_button_on_click)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.rdNoButton)
        button_layout.addWidget(self.rdYesButton)
        self.readDiaLayout = QVBoxLayout()
        self.readDiaLayout.addWidget(dlabel)
        self.readDiaLayout.addLayout(button_layout)
        self.readable_dialog.setLayout(self.readDiaLayout)
        self.readable_dialog.exec_()

    
    @ unsave_decor
    def _readable_dialog_yes_button_on_click(self):
        self.ReadableStatusDict[self.ImgIDList[self.ImgPointer]] = nr.unreadable
        self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.Modifier] = self.username
        self.modifier_label.setText('Last Modifier:\n'+self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.Modifier])
#        self.axes.set_title('Successfully set unreadable', color='red')
#        self.fig.canvas.draw_idle()
        self.next_()
#        plt.tight_layout()
        self.readable_dialog.close()
        

    def _button_grid(self):
        self.button_grid = QGridLayout()
        self.button_grid.addWidget(self.prev_button,0,0)
        self.button_grid.addWidget(self.next_button,0,1)
        self.button_grid.addWidget(self.prevun_button,1,0)
        self.button_grid.addWidget(self.nextun_button,1,1)
        self.button_grid.addWidget(self.clear_button,2,0)
        self.button_grid.addWidget(self.clearall_button,2,1)
        self.button_grid.addWidget(self.home_button,3,0)
        self.button_grid.addWidget(self.save_button,3,1)

    '''
    edit/view radiobuttons
    '''
    def _mode_radiobuttons_builer(self):
        self.mode_radiobuttons1 = QRadioButton("edit")
        self.mode_radiobuttons1.setChecked(True)
        self.mode_radiobuttons1.toggled.connect(lambda:self.view_checkbox_on_change(self.mode_radiobuttons1))
        self.mode_radiobuttons2 = QRadioButton("view")
        self.mode_radiobuttons2.toggled.connect(lambda:self.view_checkbox_on_change(self.mode_radiobuttons2))
        self.mode_vbox = QVBoxLayout()
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.mode_radiobuttons1)
        self.mode_group.addButton(self.mode_radiobuttons2)
        self.mode_vbox.addWidget(self.mode_radiobuttons1)
        self.mode_vbox.addWidget(self.mode_radiobuttons2)

#        '''
#        window level slider
#        '''
#        def _wl_slider_builder(self, min_, max_):
#            if 'wl_slider' in self.__dict__:
# #                self.mylayout.removeWidget(self.wl_slider)
#                self.up_layout.removeWidget(self.wl_slider)
#                self.wl_slider.deleteLater()
#                self.wl_slider = None

#            self.wl_slider = QRangeSlider()
#            self.wl_slider.setMin(min_)
#            self.wl_slider.setMax(max_)
#            self.wl_slider.setRange(min_,max_)
#            self.wl_slider.startValueChanged.connect(
#                lambda: self.on_wl_slider_value_change(self.wl_slider))
#            self.wl_slider.endValueChanged.connect(
#                lambda: self.on_wl_slider_value_change(self.wl_slider))

# #            self.mylayout.addWidget(self.wl_slider,2,0,2,24)
#            self.up_layout.addWidget(self.wl_slider)


    '''
    Center/corner coords tabs
    '''
    def _coord_tabs_builder(self):
        bx_coords = self._center_coords_label_builder()
        bx_cor_coords = self._corner_coords_label_builder()
        self.coords_tables = []
        box = []
        for i, vb in enumerate(self.VBLabelList):
            self.coords_tables.append(QTabWidget())
            self.bx_tab_cen = QWidget()
            self.bx_tab_cen.layout = bx_coords[i]
            self.coords_tables[i].addTab(self.bx_tab_cen, 'Center')
            self.bx_tab_cen.setLayout(self.bx_tab_cen.layout)
            self.bx_tab_cor = QWidget()
            self.bx_tab_cor.layout = bx_cor_coords[i]
            self.bx_tab_cor.setLayout(self.bx_tab_cor.layout)
            self.coords_tables[i].addTab(self.bx_tab_cor, 'Corner')
#            self.coords_tables[i].setTabPosition(QTabWidget.West)
            self.coords_tables[i].currentChanged.connect(self.on_coords_tab_change)
            box.append(QHBoxLayout())
            box[i].addWidget(self.coords_tables[i])
        return box



    '''
    Center coords labels in the table
    '''
    def _center_coords_label_builder(self):
        self.X_Label = []
        self.Y_Label = []
        bx_coords = []
        hbox = []
        for i, vb in enumerate(self.VBLabelList):
            ## coords
            self.X = QLabel("X: ", self)
            self.Y = QLabel("Y: ", self)
            self.X_Label.append(QLabel("None", self))
            self.Y_Label.append(QLabel("None", self))
            bx_X = QHBoxLayout()
            bx_X.addWidget(self.X)
            bx_X.addWidget(self.X_Label[i])
            bx_Y = QHBoxLayout()
            bx_Y.addWidget(self.Y)
            bx_Y.addWidget(self.Y_Label[i])
            hbox.append(QVBoxLayout())
            hbox[i].addLayout(bx_X)
            hbox[i].addLayout(bx_Y)
        return hbox

    '''
    Corner coords labels in the table
    '''
    def _corner_coords_label_builder(self):
        self.cor_X_Label = []
        self.cor_Y_Label = []
        bx_coords = []
        hbox = []
        for i, vb in enumerate(self.VBLabelList):
            ## coords
            self.cor_X = QLabel("X: ", self)
            self.cor_Y = QLabel("Y: ", self)
            self.cor_X_Label.append(QLabel("None", self))
            self.cor_Y_Label.append(QLabel("None", self))
            bx_X = QHBoxLayout()
            bx_X.addWidget(self.cor_X)
            bx_X.addWidget(self.cor_X_Label[i])
            bx_Y = QHBoxLayout()
            bx_Y.addWidget(self.cor_Y)
            bx_Y.addWidget(self.cor_Y_Label[i])
            hbox.append(QVBoxLayout())
            hbox[i].addLayout(bx_X)
            hbox[i].addLayout(bx_Y)
        return hbox

    '''
    fracture radiobuttons
    '''
    def _frac_radiobuttons_builder(self):
        self.frac_rb1 = []
        self.frac_rb2 = []
        self.frac_rb3 = []
        self.frac_group = []
        vbox = []
        for i, vb in enumerate(self.VBLabelList):
            self.frac_rb1.append(QRadioButton(nr.normal))
#            self.frac_rb1[i].setChecked(True)
            self.frac_rb1[i].toggled.connect(lambda:self.on_frac_radiobuttons_change(self.frac_rb1[i]))
            self.frac_rb2.append(QRadioButton(nr.ost))
            self.frac_rb2[i].toggled.connect(lambda:self.on_frac_radiobuttons_change(self.frac_rb2[i]))
            self.frac_rb3.append(QRadioButton(nr.non_ost))
            self.frac_rb3[i].toggled.connect(lambda:self.on_frac_radiobuttons_change(self.frac_rb3[i]))
            self.frac_group.append(QButtonGroup())
            self.frac_group[i].addButton(self.frac_rb1[i])
            self.frac_group[i].addButton(self.frac_rb2[i])
            self.frac_group[i].addButton(self.frac_rb3[i])
            vbox.append(QVBoxLayout())
            vbox[i].addWidget(self.frac_rb1[i])
            vbox[i].addWidget(self.frac_rb2[i])
            vbox[i].addWidget(self.frac_rb3[i])

        return vbox

    '''
    fracture VB label
    '''
    def _frac_vb_label_builder(self, type_):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Raised)
        vbox = QVBoxLayout(frame)
        if type_ == nr.ost:
            self.frac_label = QLabel(nr.ost+':')
            self.frac_vb_label = QLabel()
            self.frac_vb_label.setWordWrap(True)
            vbox.addWidget(self.frac_label)
            vbox.addWidget(self.frac_vb_label)
        elif type_ == nr.non_ost:
            self.nonost_label = QLabel(nr.non_ost+':')
            self.nonost_vb_label = QLabel()
            self.nonost_vb_label.setWordWrap(True)
            vbox.addWidget(self.nonost_label)
            vbox.addWidget(self.nonost_vb_label)
        elif type_ == nr.normal:
            self.normal_label = QLabel(nr.normal+':')
            self.normal_vb_label = QLabel()
            self.normal_vb_label.setWordWrap(True)
            vbox.addWidget(self.normal_label)
            vbox.addWidget(self.normal_vb_label)

        vbox.addStretch()
        vbox.setStretch(0,1)
        vbox.setStretch(1,4)
        vbox.setStretch(2,10)

        rst_box = QVBoxLayout()
        rst_box.addWidget(frame)
        return rst_box


    '''
    frac_type_labels_box
    '''
    def _frac_label_gather_box_builder(self):
        vbox_normal = self._frac_vb_label_builder(type_=nr.normal)
        vbox_ost = self._frac_vb_label_builder(type_=nr.ost)
        vbox_nonost = self._frac_vb_label_builder(type_=nr.non_ost)

        self.frac_label_gather_box = QVBoxLayout()
        self.frac_label_gather_box.addLayout(vbox_normal)
        self.frac_label_gather_box.addLayout(vbox_ost)
        self.frac_label_gather_box.addLayout(vbox_nonost)
        self.frac_label_gather_box.setStretch(0,1)
        self.frac_label_gather_box.setStretch(1,1)
        self.frac_label_gather_box.setStretch(2,1)

    '''
    Storing tabs
    '''
    def _storing_tabs_builder(self):
        self.table = QTabWidget()
        self.table.setTabPosition(QTabWidget.West)
#        stylesheet = """ 
#            QTabBar{background: red;}
#                    """
#        self.table.setStyleSheet(stylesheet)

        self.tabs = []
        bx_frac = self._frac_radiobuttons_builder()
        bx_coords = self._coord_tabs_builder()
        for i, vb in enumerate(self.VBLabelList):
#            widget = QTabWidget()
#            widget.setAutoFillBackground(True)
#            palette = widget.palette()
#            widget.setPalette(palette)
#            palette.setColor(widget.backgroundRole(), QtCore.Qt.red)
            self.tabs.append(QWidget())
#            self.tabs[i].setStyleSheet(stylesheet)
            self.table.addTab(self.tabs[i], vb)
            self.tabs[i].layout = QVBoxLayout()
            self.tabs[i].layout.addStretch()
            self.tabs[i].layout.addLayout(bx_frac[i])
            self.tabs[i].layout.addStretch()
            self.tabs[i].layout.addLayout(bx_coords[i])
            self.tabs[i].layout.addStretch()
            self.tabs[i].layout.setStretch(0,3)
            self.tabs[i].layout.setStretch(1,1)
            self.tabs[i].layout.setStretch(2,2)
            self.tabs[i].layout.setStretch(3,2)
            self.tabs[i].layout.setStretch(4,3)
            self.tabs[i].setLayout(self.tabs[i].layout)
        self.table.currentChanged.connect(self.on_tab_change)

    '''
    status_label_builder
    '''
    def _status_label_builder(self):
        self.status_label = QLabel('Status:\nuntouched',self)
        self.num_labelled_label = QLabel('Untouched/Total:\n' + '0/' + str(len(self.ImgIDList)), self)
        self.ImgeID_label = QLabel('Image '+str(self.ImgPointer+1)+':\n'+self.ImgIDList[self.ImgPointer],self)
        self.modifier_label = QLabel('Last Modifier:\nNone')
        self.ImgeID_label.setWordWrap(True)
        self.username_label = QLabel('Current user:\n'+self.username, self)
#            self.num_labelled_label = QLabel('Untouched/Total:\n' + '0/' + str(len(self.ImgIDList)), self)
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setFrameShadow(QFrame.Raised)
        status_box = QVBoxLayout(status_frame)
        status_box.addWidget(self.ImgeID_label)
        status_box.addWidget(self.modifier_label)
        status_box.addWidget(self.username_label)
        status_box.addWidget(self.status_label)
        status_box.addWidget(self.num_labelled_label)
        self.status_box = QVBoxLayout()
        self.status_box.addWidget(status_frame)
        

    '''
    controversial related builder
    '''
    def _controversial_ui_builder(self):
        self.controversial_label = QLabel()
        self.comment_label = QLabel()
        self.comment_label.setStyleSheet('color: red')
        self.comment_label.setWordWrap(True)
        self.comment_title_label = QLabel('Leave comments here:')
        self.comment_title_label.setWordWrap(True)
        self.comment_textbox = QTextEdit()
        self.comment_submit_button = QPushButton('submit')
        self.comment_submit_button.clicked.connect(self.comment_button_on_click)
        self.setcon_button = QPushButton('set controversial')
        self.setcon_button.clicked.connect(self.setcon_button_on_click)
        self.resetcon_button = QPushButton('reset controversial')
        self.resetcon_button.clicked.connect(self.resetcon_button_on_click)
        self.comment_clear_button = QPushButton('clear comments')
        self.comment_clear_button.clicked.connect(self.comment_clear_button_on_click)
        self.prevcon_button = QPushButton('prev controversial')
        self.prevcon_button.clicked.connect(self.prevcon_button_on_click)
        self.nextcon_button = QPushButton('next controversial')
        self.nextcon_button.clicked.connect(self.nextcon_button_on_click)

        con_frame = QFrame()
        con_frame.setFrameShape(QFrame.StyledPanel)
        con_frame.setFrameShadow(QFrame.Raised)
        controversial_box = QVBoxLayout(con_frame)

        controversial_box.addWidget(self.controversial_label)
        # related buttons
        button_box = QGridLayout()
        button_box.addWidget(self.resetcon_button,0,0)
        button_box.addWidget(self.setcon_button,0,1)
        button_box.addWidget(self.prevcon_button,1,0)
        button_box.addWidget(self.nextcon_button,1,1)
        controversial_box.addLayout(button_box)

        # comment clear button and comment label
        combutton_frame = QFrame()
        combutton_frame.setFrameShape(QFrame.StyledPanel)
        combutton_frame.setFrameShadow(QFrame.Raised)
        combutton_box = QVBoxLayout(combutton_frame)
        combutton_box.addWidget(self.comment_clear_button)
        combutton_box.addWidget(self.comment_label)
        combutton_box.setStretch(0,1)
        combutton_box.setStretch(1,5)
        controversial_box.addWidget(combutton_frame)
        
        controversial_box.addWidget(self.comment_title_label)
        controversial_box.addWidget(self.comment_textbox)
        controversial_box.addWidget(self.comment_submit_button)
        
        self.controversial_box = QVBoxLayout()
        self.controversial_box.addWidget(con_frame)

    '''
    the function of comment_submit_button
    '''
    @ unsave_decor
    def comment_button_on_click(self):
        text = self.username + '\'s idea: ' + self.comment_textbox.toPlainText() + '\n'
        self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.ConPart] += text
        self.comment_label.setText('Comments:\n'+self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.ConPart])
        self.comment_textbox.setText('')

    '''
    the function of setcon_button
    '''
    @ unsave_decor
    def setcon_button_on_click(self):
        self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.ConStatus] = nr.controversial
        self.controversial_label.setText('Is this image controversial?\nYes')
        self.controversial_label.setStyleSheet('color: red')

    '''
    the function of setcon_button
    '''
    @ unsave_decor
    def resetcon_button_on_click(self):
        self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.ConStatus] = nr.uncontroversial
        self.controversial_label.setText('Is this image controversial?\nNo')
        self.controversial_label.setStyleSheet('color: black')
    
    @ unsave_decor
    def comment_clear_button_on_click(self):
        self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.ConPart] = ''
        self.comment_label.setText('')

    """
    The function of prevcon button
    """
    @ display_decor
    def prevcon_button_on_click(self):
#            self.VBPointer = 0
        flag = False
        for i in range(1,len(self.ImgIDList)):
            index = (self.ImgPointer - i) % len(self.ImgIDList)
            if(self.ControversialDict[self.ImgIDList[index]][nr.ConStatus] == nr.controversial):
                flag = True
                break
        if flag:
            self.ImgPointer = index
#                self.UI.close()
#            self.init_display()

    """
    The function of nextcon button
    """
    @ display_decor
    def nextcon_button_on_click(self):
#            self.VBPointer = 0
        flag = False
        for i in range(1,len(self.ImgIDList)):
            index = (self.ImgPointer + i) % len(self.ImgIDList)
            if(self.ControversialDict[self.ImgIDList[index]][nr.ConStatus] == nr.controversial):
                flag = True
                break
        if flag:
            self.ImgPointer = index
#                self.UI.close()
#            self.init_display()

    '''
    buttons
    '''
    def _button_builder(self, name):
        if name == 'prev': # prev image
            self.prev_button = QPushButton('prev')
            self.prev_button.clicked.connect(self.prev)
        elif name == 'next': # next image
            self.next_button = QPushButton('next')
            self.next_button.clicked.connect(self.next_)
        elif name == 'prevun': # prev untouched image
            self.prevun_button = QPushButton('prevun')
            self.prevun_button.clicked.connect(self.prevun)
        elif name == 'nextun': # next untouched image
            self.nextun_button = QPushButton('nextun')
            self.nextun_button.clicked.connect(self.nextun)
        elif name == 'clear': # clear a pair of coordinates
            self.clear_button = QPushButton('clear')
            self.clear_button.clicked.connect(self.clear)
        elif name == 'clearall': # clear all pairs of coordinates of current image
            self.clearall_button = QPushButton('clearall')
            self.clearall_button.clicked.connect(self.clear_all)
        elif name == 'home': # restore the original image after zooming
            self.home_button = QPushButton('home')
            self.home_button.clicked.connect(self.home)
        elif name == 'save': # save the results for now
            self.save_button = QPushButton('save')
            self.save_button.clicked.connect(self.save)
        else:
            print('No connected event defined')

    '''
    the dialog to let people make sure that s/he really want to modify
    '''
    def _modify_assure_dialog(self, last_modifier):
        self.modify_dialog = QDialog()
        self.modify_dialog.setWindowTitle('Change to Edit Mode Alert!')
        dlabel = QLabel('This image was labelled by others. Are you sure you want to change to edit mode?')
        self.dNoButton = QPushButton('No')
        self.dNoButton.clicked.connect(lambda:self._dialog_no_button_on_click(last_modifier))
        self.dYesButton = QPushButton('Yes')
        self.dYesButton.clicked.connect(self.modify_dialog.accept)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.dNoButton)
        button_layout.addWidget(self.dYesButton)
        self.diaLayout = QVBoxLayout()
        self.diaLayout.addWidget(dlabel)
        self.diaLayout.addLayout(button_layout)
        self.modify_dialog.setLayout(self.diaLayout)
        self.modify_dialog.exec_()

        
        
    def _dialog_no_button_on_click(self,last_modifier):
        cur_image = self.ImgIDList[self.ImgPointer]
        self.ControversialDict[cur_image][nr.Modifier] = last_modifier
        self.mode_radiobuttons2.setChecked(True)
        self.modify_dialog.close()
#        self.modify_dialog.exec_()

    """
    What happen when view checkbox on change
    """
    def view_checkbox_on_change(self, change):
        cur_image = self.ImgIDList[self.ImgPointer]
        last_modifier = self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.Modifier]
        if self.mode == change.text():
            return
        if change.text() == nr.edit:
            self.mode = nr.edit
            if self.ControversialDict[cur_image][nr.Modifier] != None and  self.ControversialDict[cur_image][nr.Modifier] != self.username:
                self.ControversialDict[cur_image][nr.Modifier] = self.username
                self._modify_assure_dialog(last_modifier)
                self.modifier_label.setText('Last Modifier:\n'+self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.Modifier])
        else:
            self.mode = nr.view


#        """
#        window level slider function
#        """
#        def on_wl_slider_value_change(self, change):
# #            assert False
#            self.cur_min_intensity = self.wl_slider.start()
#            self.cur_max_intensity = self.wl_slider.end()
# #            print(self.cur_min_intensity, self.cur_max_intensity )
#            self.update_display()


    """
    What happen when fracture radiobutton on change
    """
    def on_frac_radiobuttons_change(self, change):
        cur_imgID = self.ImgIDList[self.ImgPointer]
        cur_sdict = self.StoreDict[cur_imgID]
        cur_VB = self.VBLabelList[self.VBPointer]
        if self.mode != nr.edit:
            if cur_sdict[cur_VB][nr.Fracture] != None:
                if cur_sdict[cur_VB][nr.Fracture] == nr.normal:
                    self.frac_rb1[self.VBPointer].setChecked(True)
                elif cur_sdict[cur_VB][nr.Fracture] == nr.ost:
                    self.frac_rb2[self.VBPointer].setChecked(True)
                elif cur_sdict[cur_VB][nr.Fracture] == nr.non_ost:
                    self.frac_rb3[self.VBPointer].setChecked(True)

            else:
                self.frac_rb1[self.VBPointer].setChecked(True)
            return
        # when changing the radio buttons, this function will be called two times
        # the first time change.text() = previous button text, because it's unchecked
        # the second time change.text() = changed button text, because it's checked
        # we need to judge whether it's first called or second called
        original_frac = self.StoreDict[cur_imgID][cur_VB][nr.Fracture]
        if original_frac != change.text():
            self.StoreDict[cur_imgID][cur_VB][nr.Fracture] = change.text()
            self.update_status()
            self.update_display()
            self.update_frac_vb_label()
            self.ControversialDict[cur_imgID][nr.Modifier] = self.username
            if not self.is_update_table\
                   and self.StoreDict[cur_imgID][cur_VB][nr.Coords][0] != None \
                   and self.StoreDict[cur_imgID][cur_VB][nr.Coords][1] != None \
                and self.StoreDict[cur_imgID][cur_VB][nr.CorCoords][0] != None \
                and self.StoreDict[cur_imgID][cur_VB][nr.CorCoords][1] != None:
                self.VBPointer += 1
                self.table.setCurrentIndex(self.VBPointer)
        if original_frac != change.text() and not self.init_display_flag:
            self.save_status = nr.unsaved
            self.update_save_status_label()


    """
    What happen when coords tabs on change (i.e., the activated VB changes)
    """
    def on_coords_tab_change(self, change):
        self.CoordType = self.CoordTypeList[change]

    """
    What happen when storing tabs on change (i.e., the activated VB changes)
    """
    def on_tab_change(self, change):
#            assert False
        self.VBPointer = change
        self.update_coord_tabs()


    """
    The function of prev button
    """
    @ display_decor
    def prev(self):
#            self.VBPointer = 0
        self.ImgPointer = (self.ImgPointer - 1) % len(self.ImgIDList)
#            self.UI.close()
#        self.init_display()



    """
    The function of next button
    """
    @ display_decor
    def next_(self):
#            self.VBPointer = 0
        self.ImgPointer = (self.ImgPointer + 1) % len(self.ImgIDList)
#            self.UI.close()
#        self.init_display()

    """
    The function of prevun button
    """
    @ display_decor
    def prevun(self):
#            self.VBPointer = 0
        flag = False
        for i in range(1,len(self.ImgIDList)):
            index = (self.ImgPointer - i) % len(self.ImgIDList)
            if(self.StatusDict[self.ImgIDList[index]] == nr.untouch):
                flag = True
                break
        if flag:
            self.ImgPointer = index
#                self.UI.close()
#            self.init_display()

    """
    The function of nextun button
    """
    @ display_decor
    def nextun(self):
#            self.VBPointer = 0
        flag = False
        for i in range(1,len(self.ImgIDList)):
            index = (self.ImgPointer + i) % len(self.ImgIDList)
            if(self.StatusDict[self.ImgIDList[index]] == nr.untouch):
                flag = True
                break
        if flag:
            self.ImgPointer = index
#                self.UI.close()
#            self.init_display()

    """
    The function of clearall button: clear all the info of current image
    """
    @ unsave_decor
    def clear_all(self):
        if self.mode != nr.edit:
            return
        cur_imgID = self.ImgIDList[self.ImgPointer]
        self.ControversialDict[cur_imgID][nr.Modifier] = self.username
        for i, vb in enumerate(self.VBLabelList):
            self.StoreDict[cur_imgID][vb][nr.Coords] = (None,None)
            self.StoreDict[cur_imgID][vb][nr.CorCoords] = (None,None)
            self.StoreDict[cur_imgID][vb][nr.Fracture] = nr.normal
        self.update_status()
        self.update_display()
        self.VBPointer = 0
        self.table.setCurrentIndex(0)
        self.CoordType = self.CoordTypeList[0]
        self.coords_tables[self.VBPointer].setCurrentIndex(0)
        self.update_table()



    """
    The function of clear button: clear the info of the current VB
    """
    @ unsave_decor
    def clear(self):
        if self.mode != nr.edit:
            return
        cur_imgID = self.ImgIDList[self.ImgPointer]
        cur_VB = self.VBLabelList[self.VBPointer]

        self.ControversialDict[cur_imgID][nr.Modifier] = self.username
        if self.CoordType == self.CoordTypeList[0]:
            self.StoreDict[cur_imgID][cur_VB][nr.Coords] = (None,None)
        else:
            self.StoreDict[cur_imgID][cur_VB][nr.CorCoords] = (None,None)
#            self.StoreDict[cur_imgID][cur_VB][nr.Fracture] = nr.normal
        self.update_status()
        self.update_display()
        self.update_table()


    """
    Function of home button: restore the original image after zooming
    """
    def home(self, button):
        self.axes.set_xlim(0,len(self.npa[0]))
        self.axes.set_ylim(len(self.npa),0)
        self.cur_min_intensity = self.min_intensity
        self.cur_max_intensity = self.max_intensity
        self.update_display()


    """
    The function of save button: save current StoreDict and StatusDict into the csv file
    """
    def save(self, button):
        csv_cols = nr.csv_headers
        with open(self.fpath, 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=csv_cols)
            writer.writeheader()
            if self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.Modifier] == None:
                self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.Modifier] = self.username
                self.modifier_label.setText('Last Modifier:\n'+self.ControversialDict[self.ImgIDList[self.ImgPointer]][nr.Modifier])
            for ID in self.ImgIDList:
                status = self.StatusDict[ID]
                VB_dict = self.StoreDict[ID]
                mod = self.ControversialDict[ID][nr.Modifier]
                con_status = self.ControversialDict[ID][nr.ConStatus]
                con_part = self.ControversialDict[ID][nr.ConPart]
                readable = self.ReadableStatusDict[ID]
                for i, vb in enumerate(self.VBLabelList):
                    x = VB_dict[vb][nr.Coords][0]
                    y = VB_dict[vb][nr.Coords][1]
                    cor_x = VB_dict[vb][nr.CorCoords][0]
                    cor_y = VB_dict[vb][nr.CorCoords][1]
                    f = VB_dict[vb][nr.Fracture]
                    csv_dict = {
                                nr.head_imgID: ID,
                                nr.head_status: status,
                                nr.head_vbLabel: vb,
                                nr.head_cenX: x, nr.head_cenY: y,
                                nr.head_corX: cor_x, nr.head_corY: cor_y,
                                nr.head_frac:f,
                                nr.head_modifier: mod,
                                nr.head_conStatus: con_status,
                                nr.head_conParts: con_part,
                                nr.head_readableStatus: readable
                                }
                    writer.writerow(csv_dict)
        self.save_status = nr.saved
        self.update_save_status_label()


    """
    What to do after clicking on image
    """
    def image_click(self, event):
        # left click
        if event.inaxes==self.axes:
            if event.button == 1:
                if not event.dblclick:
                    if self.mode == nr.edit:
                        cur_imgID = self.ImgIDList[self.ImgPointer]
                        cur_VB = self.VBLabelList[self.VBPointer]
                        self.ControversialDict[cur_imgID][nr.Modifier] = self.username
                        if self.CoordType == self.CoordTypeList[0]:
                            self.StoreDict[cur_imgID][cur_VB][nr.Coords] = (event.xdata, event.ydata)
                        else:
                            self.StoreDict[cur_imgID][cur_VB][nr.CorCoords] = (event.xdata, event.ydata)

                        self.update_status()
                        self.update_display()
                        self.update_table()
                        if self.CoordType == self.CoordTypeList[1]:
                            # activate the next VB automatically
                            self.VBPointer = (self.VBPointer + 1)%len(self.VBLabelList)
                            self.table.setCurrentIndex(self.VBPointer)
                        self.update_coord_tabs()
                        self.save_status = nr.unsaved
                        self.update_save_status_label()
            elif event.button == 3:
                if event.dblclick:
                    # no zooming
                    if self.key_press == None:
                        self.axes.set_xlim(0,len(self.npa[0]))
                        self.axes.set_ylim(len(self.npa),0)
                    # original window label
                    else:
                        self.cur_min_intensity = self.min_intensity
                        self.cur_max_intensity = self.max_intensity
                    self.update_display()
                else:
                    self.press = event.xdata, event.ydata

    """
    Mouse motion after mouse right single click
    """
    def on_motion(self, event):
        'on motion we will move the rect if the mouse is over us'
        if self.press is None and self.key_press is None: return
        if event.inaxes != self.axes: return
        if self.press != None:
            xpress, ypress = self.press
            dx = event.xdata - xpress
            dy = event.ydata - ypress
            cur_xlim = self.axes.get_xlim()
            cur_ylim = self.axes.get_ylim()
            self.axes.set_xlim([cur_xlim[0] - dx, cur_xlim[1] - dx])
            self.axes.set_ylim([cur_ylim[0] - dy, cur_ylim[1] - dy])
            self.update_display()
        if self.key_press != None:
            xpress, ypress = self.key_press
            gray_range = self.max_intensity - self.min_intensity
            dx = event.xdata - xpress
            dy = event.ydata - ypress
            if abs(dx) > abs(dy):
                cur_xlim = self.axes.get_xlim()
                x_range = cur_xlim[1] - cur_xlim[0]
                dgray = gray_range * (dx / x_range)*self.wl_scale
                if self.cur_max_intensity + dgray < self.max_intensity \
                    and self.cur_max_intensity + dgray > self.cur_min_intensity:
                    self.cur_max_intensity += dgray
            else:
                cur_ylim = self.axes.get_ylim()
                y_range = cur_ylim[1] - cur_ylim[0]
                dgray = gray_range * (dy / y_range)*self.wl_scale
                if self.cur_min_intensity + dgray > self.min_intensity \
                    and self.cur_min_intensity + dgray < self.cur_max_intensity:
                    self.cur_min_intensity += dgray
#                print(self.cur_min_intensity, self.cur_max_intensity)
#                self.wl_slider.setStart(self.cur_min_intensity)
#                self.wl_slider.setEnd(self.cur_max_intensity)
            self.update_display()

    """
    Mouse release after motion
    """
    def on_release(self, event):
        'on release we reset the press data'
        self.press = None
        self.update_display()


    """
    key press
    """
    def on_key_press(self, event):
#            assert False
        sys.stdout.flush()
#            print(self.key_press)
        if event.key == 'control':
#                assert False
            self.key_press = event.xdata, event.ydata
#                print(self.key_press)

    """
    key release
    """
    def on_key_release(self, event):
        self.key_press = None
        self.update_display()
#            print(self.key_press)

    """
    What to do after scolling
    """
    def scoll_zoom(self, event):
        # get the current x and y limits
        cur_xlim = self.axes.get_xlim()
        cur_ylim = self.axes.get_ylim()
#            cur_xrange = (cur_xlim[1] - cur_xlim[0])*.5
#            cur_yrange = (cur_ylim[1] - cur_ylim[0])*.5
        xdata = event.xdata # get event x location
        ydata = event.ydata # get event y location
        left_xdata = xdata - cur_xlim[0]
        right_xdata = cur_xlim[1] - xdata
        up_ydata = ydata - cur_ylim[0]
        down_ydata = cur_ylim[1] - ydata
        if event.button == 'down':
            # deal with zoom in
            scale_factor = 1/self.zoom_base_scale
        elif event.button == 'up':
            # deal with zoom out
            scale_factor = self.zoom_base_scale
        else:
            # deal with something that should never happen
            scale_factor = 1
#                print(event.button)
        # set new limits
        self.axes.set_xlim([xdata - left_xdata*scale_factor,
                 xdata + right_xdata*scale_factor])
        self.axes.set_ylim([ydata - up_ydata*scale_factor,
                 ydata + down_ydata*scale_factor])
        self.update_display()





